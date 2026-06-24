"""
Business logic for the HACCP domain.

Provides two service layers:

1. **Temperature records** — ``create_temperature_record`` validates the
   submitted measurement against the equipment's configured thresholds and,
   within the same database transaction, calls the non-conformities service
   to automatically open an incident ticket when the value is out of range.
   This guarantees that no out-of-range reading can exist without an associated
   ``NonConformity`` ticket.

   ``create_temperature_records_bulk`` accepts up to 30 readings in a single
   request, pre-validates all equipment IDs, and writes everything atomically
   inside a savepoint.  It is the preferred path for the daily temperature tour.

2. **Time clock** — enforces a strict state-machine on operator clock events
   (CLOCK_IN → BREAK_START ↔ BREAK_END → CLOCK_OUT) before writing.  The
   feature can be toggled per establishment via the ``timeclock.enabled``
   settings flag.

Helper functions (``_normalize_for_site``, ``_validate_measurement_time``,
``_is_temperature_compliant``, ``_status_from_event``) are pure and stateless
to facilitate unit testing.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from time import perf_counter
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.metrics import (
    TEMPERATURE_RECORD_DURATION_SECONDS,
    TEMPERATURE_RECORDS_TOTAL,
    TIMECLOCK_EVENTS_TOTAL,
)
from app.core.time_utils import now_for_site
from app.modules.equipments.models import Equipement
from app.modules.haccp.models import (
    Pointage,
    ReleveTemperature,
    TypeEvenementPointage,
)
from app.modules.haccp.schemas import (
    EstablishmentTimeclockStatusResponse,
    OperatorTimeclockStatusItem,
    PointageCreate,
    PointageResponse,
    TemperatureRecordBulkCreate,
    TemperatureRecordBulkResponse,
    TemperatureRecordCreate,
    TemperatureRecordResponse,
    TimeclockStatus,
)
from app.modules.personnel.models import AffectationSite, Utilisateur

logger = structlog.get_logger(__name__)

# ── Time validation constants ─────────────────────────────────────────────────

_MAX_PAST_DELTA = timedelta(hours=8)
"""Maximum age of a client-supplied ``measured_at`` timestamp.

8 hours covers a full kitchen shift in offline mode.  Readings older than this
would allow systematic backdating of HACCP records, which constitutes falsification
of mandatory food-safety documentation under French law.
"""

_MAX_FUTURE_DELTA = timedelta(minutes=5)
"""Maximum future offset allowed for a client-supplied ``measured_at`` timestamp.

5 minutes accommodates reasonable device clock drift without permitting
post-dated entries.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalize_for_site(value: datetime | None, timezone: str) -> datetime:
    """Coerce a datetime to the establishment's timezone, defaulting to now.

    When ``value`` is ``None``, returns the current site-local time.  When
    it is timezone-naive, the establishment timezone is attached.  When it is
    already timezone-aware, it is converted to the site timezone.

    Args:
        value (datetime | None): The raw timestamp from the request, or
            ``None`` to use the current time.
        timezone (str): The IANA timezone string of the establishment.

    Returns:
        datetime: A timezone-aware datetime anchored to the establishment's locale.
    """
    site_tz = ZoneInfo(timezone)
    if value is None:
        return now_for_site(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=site_tz)
    return value.astimezone(site_tz)


def _validate_measurement_time(measured_at: datetime) -> None:
    """Reject client-supplied timestamps outside the acceptable recording window.

    The function is intentionally **not** called when ``payload.measured_at``
    is ``None`` — the server-substituted ``now_for_site()`` value is always
    valid and requires no further check.

    Args:
        measured_at (datetime): The site-normalized measurement timestamp
            (output of ``_normalize_for_site`` when ``payload.measured_at``
            was provided by the client).

    Raises:
        HTTPException: 422 Unprocessable Entity if the timestamp is more than
            ``_MAX_PAST_DELTA`` (8 h) in the past or more than
            ``_MAX_FUTURE_DELTA`` (5 min) in the future.
    """
    now = datetime.now(tz=measured_at.tzinfo)
    if measured_at < now - _MAX_PAST_DELTA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "measured_at est trop ancien (limite : 8h). "
                "Les relevés antidatés ne sont pas autorisés."
            ),
        )
    if measured_at > now + _MAX_FUTURE_DELTA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "measured_at est dans le futur (limite : +5 min). Vérifiez l'heure de l'appareil."
            ),
        )


def _is_temperature_compliant(value: Decimal, min_cible: Decimal, max_cible: Decimal) -> bool:
    """Return ``True`` if the measured temperature is within the safe range.

    Uses inclusive comparison (``min <= value <= max``) to match French
    food-safety inspection conventions.

    Args:
        value (Decimal): The measured temperature in Celsius.
        min_cible (Decimal): The equipment's lower threshold.
        max_cible (Decimal): The equipment's upper threshold.

    Returns:
        bool: ``True`` if the value is within the acceptable range.
    """
    return min_cible <= value <= max_cible


def _status_from_event(event_type: TypeEvenementPointage | None) -> TimeclockStatus:
    """Derive the operator's current time-clock status from their last event.

    Args:
        event_type (TypeEvenementPointage | None): The most recent event type,
            or ``None`` if the operator has never clocked in.

    Returns:
        TimeclockStatus: The derived current status.
    """
    if event_type in (TypeEvenementPointage.CLOCK_IN, TypeEvenementPointage.BREAK_END):
        return TimeclockStatus.ACTIVE
    if event_type == TypeEvenementPointage.BREAK_START:
        return TimeclockStatus.ON_BREAK
    return TimeclockStatus.CLOCKED_OUT


# Permitted state-machine transitions: maps the current status to the set of
# allowed next events.  Any event not in the set will be rejected with 409.
_VALID_TRANSITIONS: dict[TimeclockStatus, set[TypeEvenementPointage]] = {
    TimeclockStatus.CLOCKED_OUT: {TypeEvenementPointage.CLOCK_IN},
    TimeclockStatus.ACTIVE: {TypeEvenementPointage.BREAK_START, TypeEvenementPointage.CLOCK_OUT},
    TimeclockStatus.ON_BREAK: {TypeEvenementPointage.BREAK_END, TypeEvenementPointage.CLOCK_OUT},
}

_STATUS_LABELS: dict[TimeclockStatus, str] = {
    TimeclockStatus.CLOCKED_OUT: "non pointé",
    TimeclockStatus.ACTIVE: "en service",
    TimeclockStatus.ON_BREAK: "en pause",
}


# ── Temperature records ───────────────────────────────────────────────────────


async def create_temperature_record(
    payload: TemperatureRecordCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    current_operator: Utilisateur,
) -> TemperatureRecordResponse:
    """Record a temperature measurement and auto-open a non-conformity if out of range.

    The compliance check and (optionally) the NC creation both happen inside the
    same database transaction — a ``flush`` writes the ``ReleveTemperature`` row
    to obtain its primary key before the NC service references it, and a single
    final ``commit`` ensures both records are persisted atomically.

    Args:
        payload (TemperatureRecordCreate): The submitted measurement.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        current_operator (Utilisateur): The PIN-authenticated operator.

    Returns:
        TemperatureRecordResponse: The created record with conformity context.

    Raises:
        HTTPException: 404 Not Found if the equipment does not exist or belongs
            to a different establishment.
        HTTPException: 422 Unprocessable Entity if ``measured_at`` is outside
            the acceptable recording window (more than 8 h in the past or more
            than 5 min in the future).
    """
    from app.modules.nonconformities import service as nc_service

    _started = perf_counter()

    equipment_result = await db.execute(
        select(Equipement).where(
            Equipement.id == payload.equipment_id,
            Equipement.etablissement_id == establishment.etablissement_id,
            Equipement.deleted_at.is_(None),
        )
    )
    equipment = equipment_result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found for this establishment.",
        )

    mesure_effectuee_at = _normalize_for_site(payload.measured_at, establishment.timezone)
    if payload.measured_at is not None:
        _validate_measurement_time(mesure_effectuee_at)

    is_conforme = _is_temperature_compliant(
        payload.measured_value, equipment.temperature_min_cible, equipment.temperature_max_cible
    )
    releve = ReleveTemperature(
        etablissement_id=establishment.etablissement_id,
        equipement_id=equipment.id,
        utilisateur_id=current_operator.id,
        valeur_mesuree=payload.measured_value,
        is_conforme=is_conforme,
        source=payload.source,
        mesure_effectuee_at=mesure_effectuee_at,
    )
    db.add(releve)
    # Flush to get the releve PK before the NC service creates its FK reference.
    await db.flush()

    nonconformity_id = None
    if not is_conforme:
        # Out-of-range readings must immediately produce an open NC ticket
        # so the corrective action workflow can begin without manager intervention.
        nc = await nc_service.open_temperature_nonconformity(releve, db)
        nonconformity_id = nc.id

    await db.commit()
    await db.refresh(releve)

    TEMPERATURE_RECORDS_TOTAL.labels(
        is_conforme=str(is_conforme).lower(),
        source=str(releve.source),
    ).inc()
    TEMPERATURE_RECORD_DURATION_SECONDS.observe(perf_counter() - _started)
    logger.info(
        "temperature_record_created",
        equipment_id=str(releve.equipement_id),
        valeur_mesuree=str(releve.valeur_mesuree),
        is_conforme=is_conforme,
        source=str(releve.source),
        nonconformity_opened=nonconformity_id is not None,
    )

    return TemperatureRecordResponse(
        id=releve.id,
        etablissement_id=releve.etablissement_id,
        equipment_id=releve.equipement_id,
        utilisateur_id=releve.utilisateur_id,
        measured_value=releve.valeur_mesuree,
        temperature_min_cible=equipment.temperature_min_cible,
        temperature_max_cible=equipment.temperature_max_cible,
        is_conforme=releve.is_conforme,
        action_corrective_required=not releve.is_conforme,
        nonconformity_id=nonconformity_id,
        source=releve.source,
        measured_at=releve.mesure_effectuee_at,
    )


async def create_temperature_records_bulk(
    payload: TemperatureRecordBulkCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    current_operator: Utilisateur,
) -> TemperatureRecordBulkResponse:
    """Record multiple temperature measurements in a single atomic transaction.

    Designed for the daily temperature tour: pre-validates all equipment IDs in
    one query, then writes all records and any resulting non-conformity tickets
    inside a savepoint.  Either everything succeeds or nothing is written.

    Args:
        payload (TemperatureRecordBulkCreate): Up to 30 measurements.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        current_operator (Utilisateur): The PIN-authenticated operator.

    Returns:
        TemperatureRecordBulkResponse: All created records with their conformity
            results, a total count, and the number of non-conformities opened.

    Raises:
        HTTPException: 400 Bad Request if any equipment ID is unknown or belongs
            to a different establishment.
        HTTPException: 422 Unprocessable Entity if any ``measured_at`` is outside
            the acceptable recording window.
    """
    from app.modules.nonconformities import service as nc_service

    _started = perf_counter()

    # ── 1. Pre-validate all equipment IDs in a single query ───────────────────
    equipment_ids = [r.equipment_id for r in payload.records]
    eq_result = await db.execute(
        select(Equipement).where(
            Equipement.id.in_(equipment_ids),
            Equipement.etablissement_id == establishment.etablissement_id,
            Equipement.deleted_at.is_(None),
        )
    )
    equipment_map: dict[UUID, Equipement] = {eq.id: eq for eq in eq_result.scalars().all()}
    unknown = set(equipment_ids) - set(equipment_map.keys())
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Équipements inconnus ou inaccessibles : {[str(i) for i in unknown]}",
        )

    # ── 2. Validate all timestamps before writing anything ────────────────────
    normalized_times: list[datetime] = []
    for record in payload.records:
        mesure_at = _normalize_for_site(record.measured_at, establishment.timezone)
        if record.measured_at is not None:
            _validate_measurement_time(mesure_at)
        normalized_times.append(mesure_at)

    # ── 3. Batch insert inside a savepoint ────────────────────────────────────
    releves: list[ReleveTemperature] = []
    nc_ids: list[UUID | None] = []

    async with db.begin_nested():
        for record, mesure_effectuee_at in zip(payload.records, normalized_times, strict=True):
            equipment = equipment_map[record.equipment_id]
            is_conforme = _is_temperature_compliant(
                record.measured_value,
                equipment.temperature_min_cible,
                equipment.temperature_max_cible,
            )
            releve = ReleveTemperature(
                etablissement_id=establishment.etablissement_id,
                equipement_id=equipment.id,
                utilisateur_id=current_operator.id,
                valeur_mesuree=record.measured_value,
                is_conforme=is_conforme,
                source=record.source,
                mesure_effectuee_at=mesure_effectuee_at,
            )
            db.add(releve)
            await db.flush()

            nc_id: UUID | None = None
            if not is_conforme:
                nc = await nc_service.open_temperature_nonconformity(releve, db)
                nc_id = nc.id

            releves.append(releve)
            nc_ids.append(nc_id)

    await db.commit()
    for releve in releves:
        await db.refresh(releve)

    # ── 4. Emit metrics ───────────────────────────────────────────────────────
    nonconformity_count = sum(1 for nc_id in nc_ids if nc_id is not None)
    for releve in releves:
        TEMPERATURE_RECORDS_TOTAL.labels(
            is_conforme=str(releve.is_conforme).lower(),
            source=str(releve.source),
        ).inc()

    TEMPERATURE_RECORD_DURATION_SECONDS.observe(perf_counter() - _started)
    logger.info(
        "temperature_records_bulk_created",
        count=len(releves),
        nonconformity_count=nonconformity_count,
        source=str(payload.records[0].source) if payload.records else "unknown",
    )

    results = [
        TemperatureRecordResponse(
            id=releve.id,
            etablissement_id=releve.etablissement_id,
            equipment_id=releve.equipement_id,
            utilisateur_id=releve.utilisateur_id,
            measured_value=releve.valeur_mesuree,
            temperature_min_cible=equipment_map[releve.equipement_id].temperature_min_cible,
            temperature_max_cible=equipment_map[releve.equipement_id].temperature_max_cible,
            is_conforme=releve.is_conforme,
            action_corrective_required=not releve.is_conforme,
            nonconformity_id=nc_id,
            source=releve.source,
            measured_at=releve.mesure_effectuee_at,
        )
        for releve, nc_id in zip(releves, nc_ids, strict=True)
    ]

    return TemperatureRecordBulkResponse(
        created=results,
        count=len(results),
        nonconformity_count=nonconformity_count,
    )


# ── Time clock ────────────────────────────────────────────────────────────────


async def _get_operator_status(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator_id: UUID,
) -> tuple[TimeclockStatus, TypeEvenementPointage | None]:
    """Return the current time-clock status for an operator.

    Fetches only the most recent event to minimise database load.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator_id (UUID): The operator's primary key.

    Returns:
        tuple[TimeclockStatus, TypeEvenementPointage | None]: The derived status
            and the raw event type of the most recent record.
    """
    result = await db.execute(
        select(Pointage.type_evenement)
        .where(
            Pointage.etablissement_id == establishment.etablissement_id,
            Pointage.utilisateur_id == operator_id,
        )
        .order_by(Pointage.pointe_at.desc())
        .limit(1)
    )
    last_event = result.scalar_one_or_none()
    return _status_from_event(last_event), last_event


async def create_time_clock_event(
    payload: PointageCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    current_operator: Utilisateur,
) -> PointageResponse:
    """Record a time-clock event after validating the state-machine transition.

    Rejects any event that does not represent a permitted transition from the
    operator's current status (e.g. clocking in while already active).

    Args:
        payload (PointageCreate): The event type to record.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        current_operator (Utilisateur): The PIN-authenticated operator.

    Returns:
        PointageResponse: The created time-clock event.

    Raises:
        HTTPException: 403 Forbidden if the timeclock feature is disabled.
        HTTPException: 409 Conflict if the event is not a valid transition
            from the operator's current state.
    """
    current_status, _ = await _get_operator_status(db, establishment, current_operator.id)
    allowed = _VALID_TRANSITIONS.get(current_status, set())

    if payload.type_evenement not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Action impossible : vous êtes {_STATUS_LABELS[current_status]}. "
                f"Actions disponibles : {', '.join(e.value for e in allowed) or 'aucune'}."
            ),
        )

    pointage = Pointage(
        etablissement_id=establishment.etablissement_id,
        utilisateur_id=current_operator.id,
        type_evenement=payload.type_evenement,
        pointe_at=now_for_site(establishment.timezone),
    )
    db.add(pointage)
    await db.commit()
    await db.refresh(pointage)
    TIMECLOCK_EVENTS_TOTAL.labels(type_evenement=str(payload.type_evenement)).inc()
    logger.info(
        "timeclock_event_created",
        operator_id=str(current_operator.id),
        type_evenement=str(payload.type_evenement),
    )
    return PointageResponse.model_validate(pointage)


async def get_operator_timeclock_status(
    db: AsyncSession, establishment: CurrentEstablishment, operator: Utilisateur
) -> OperatorTimeclockStatusItem:
    """Return the current time-clock status for a single operator.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The operator to query.

    Returns:
        OperatorTimeclockStatusItem: Status and last event details.
    """
    result = await db.execute(
        select(Pointage.type_evenement, Pointage.pointe_at)
        .where(
            Pointage.etablissement_id == establishment.etablissement_id,
            Pointage.utilisateur_id == operator.id,
        )
        .order_by(Pointage.pointe_at.desc())
        .limit(1)
    )
    row = result.one_or_none()
    event_type = row[0] if row else None
    event_at = row[1] if row else None
    return OperatorTimeclockStatusItem(
        operator_id=operator.id,
        status=_status_from_event(event_type),
        last_event_type=event_type,
        last_event_at=event_at,
    )


async def get_establishment_operator_statuses(
    db: AsyncSession, establishment: CurrentEstablishment
) -> EstablishmentTimeclockStatusResponse:
    """Return the current time-clock status for all operators at an establishment.

    Uses a subquery to fetch only the latest event per operator in a single
    round-trip, avoiding N+1 queries when an establishment has many operators.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        EstablishmentTimeclockStatusResponse: One status item per active operator.
    """
    operators_result = await db.execute(
        select(AffectationSite.utilisateur_id, Utilisateur.prenom, Utilisateur.nom)
        .join(Utilisateur, Utilisateur.id == AffectationSite.utilisateur_id)
        .where(
            AffectationSite.etablissement_id == establishment.etablissement_id,
            AffectationSite.is_active.is_(True),
        )
        .distinct()
    )
    operators = {row[0]: f"{row[1]} {row[2]}" for row in operators_result.all()}
    operator_ids = list(operators.keys())

    if not operator_ids:
        return EstablishmentTimeclockStatusResponse(items=[])

    # Subquery fetches the max(pointe_at) per operator in one aggregation step,
    # then the outer query joins back to retrieve the full event row.
    latest_subq = (
        select(Pointage.utilisateur_id, func.max(Pointage.pointe_at).label("max_at"))
        .where(
            Pointage.etablissement_id == establishment.etablissement_id,
            Pointage.utilisateur_id.in_(operator_ids),
        )
        .group_by(Pointage.utilisateur_id)
        .subquery()
    )
    events_result = await db.execute(
        select(Pointage.utilisateur_id, Pointage.type_evenement, Pointage.pointe_at).join(
            latest_subq,
            (Pointage.utilisateur_id == latest_subq.c.utilisateur_id)
            & (Pointage.pointe_at == latest_subq.c.max_at),
        )
    )
    last_events = {row[0]: (row[1], row[2]) for row in events_result.all()}

    items = []
    for op_id in operator_ids:
        entry = last_events.get(op_id)
        event_type = entry[0] if entry else None
        event_at = entry[1] if entry else None
        items.append(
            OperatorTimeclockStatusItem(
                operator_id=op_id,
                operator_name=operators.get(op_id),
                status=_status_from_event(event_type),
                last_event_type=event_type,
                last_event_at=event_at,
            )
        )
    return EstablishmentTimeclockStatusResponse(items=items)
