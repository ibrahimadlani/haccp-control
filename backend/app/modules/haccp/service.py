"""
Business logic for the HACCP domain.

Provides two service layers:

1. **Temperature records** — ``create_temperature_record`` validates the
   submitted measurement against the equipment's configured thresholds and,
   within the same database transaction, calls the non-conformities service
   to automatically open an incident ticket when the value is out of range.
   This guarantees that no out-of-range reading can exist without an associated
   ``NonConformity`` ticket.

2. **Time clock** — enforces a strict state-machine on operator clock events
   (CLOCK_IN → BREAK_START ↔ BREAK_END → CLOCK_OUT) before writing.  The
   feature can be toggled per establishment via the ``timeclock.enabled``
   settings flag.

Helper functions (``_normalize_for_site``, ``_is_temperature_compliant``,
``_status_from_event``) are pure and stateless to facilitate unit testing.
"""

from datetime import datetime
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
    TemperatureRecordCreate,
    TemperatureRecordResponse,
    TimeclockStatus,
)
from app.modules.personnel.models import AffectationSite, Utilisateur

logger = structlog.get_logger(__name__)

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
        mesure_effectuee_at=_normalize_for_site(payload.measured_at, establishment.timezone),
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
