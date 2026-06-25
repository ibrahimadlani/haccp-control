"""
Business logic for the Non-Conformities domain.

Manages the four-state lifecycle of HACCP incident tickets:

``OPEN → IN_PROGRESS → RESOLVED → CLOSED``

**Public API:**

- ``open_temperature_nonconformity`` — called from the HACCP service within
  the same transaction that creates a ``ReleveTemperature`` record.  Flushes
  (not commits) so the NC ID is available for the temperature response.

- ``list_nonconformities`` — manager-facing filtered list with status counts.

- ``get_nonconformity_stats`` — lightweight status counters without loading
  full item payloads.

- ``acknowledge_nonconformity`` — transitions OPEN → IN_PROGRESS.

- ``create_corrective_action`` — transitions IN_PROGRESS → RESOLVED.  Accepts
  an optional photo upload, stores only the S3 key (never a presigned URL).

- ``close_nonconformity`` — manager-only transition RESOLVED → CLOSED.

All state transitions validate the current status and raise 409 Conflict for
invalid transitions, providing a clear error message that includes the current
status to help the frontend recover gracefully.

Private helpers ``_deviation_celsius`` and ``_build_item`` are pure/idempotent
and testable without a database.  ``_load_nonconformity`` is the shared
tenant-scoped lookup used by all lifecycle operations.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.metrics import (
    NONCONFORMITIES_CLOSED_TOTAL,
    NONCONFORMITIES_OPENED_TOTAL,
    NONCONFORMITIES_RESOLVED_TOTAL,
    NONCONFORMITY_RESOLUTION_SECONDS,
)
from app.core.s3 import S3Service
from app.core.time_utils import now_for_site
from app.modules.equipments.models import Equipement
from app.modules.haccp.models import ReleveTemperature
from app.modules.haccp.schemas import ActionCorrectiveResponse
from app.modules.nonconformities.models import (
    ActionCorrective,
    NonConformity,
    NonConformityStatus,
    WorkflowType,
)
from app.modules.nonconformities.schemas import (
    CloseNonConformityRequest,
    NonConformityItemResponse,
    NonConformityListResponse,
    NonConformityStatsResponse,
)
from app.modules.personnel.models import Utilisateur
from app.modules.personnel.service import ensure_admin_org_access

logger = structlog.get_logger(__name__)


def _deviation_celsius(measured: Decimal, min_target: Decimal, max_target: Decimal) -> Decimal:
    """Compute the absolute deviation from the nearest threshold boundary.

    Args:
        measured (Decimal): The recorded temperature value.
        min_target (Decimal): The equipment's lower safe threshold.
        max_target (Decimal): The equipment's upper safe threshold.

    Returns:
        Decimal: The positive distance from the closest boundary, or
            ``Decimal("0")`` if the value is within range.
    """
    if measured < min_target:
        return min_target - measured
    if measured > max_target:
        return measured - max_target
    return Decimal("0")


def _build_item(nc: NonConformity, s3: S3Service | None = None) -> NonConformityItemResponse:
    """Assemble a ``NonConformityItemResponse`` from a loaded ORM instance.

    Denormalises related data (operator names, equipment details, corrective
    action) into a flat response.  The ``s3`` parameter is optional; when
    ``None``, photo URLs are not generated (used in contexts where S3 is not
    needed, e.g. internal calls from the receptions module).

    Args:
        nc (NonConformity): The NC ORM instance with all relationships loaded.
        s3 (S3Service | None): S3 service for building photo URLs.

    Returns:
        NonConformityItemResponse: The flat response DTO.
    """
    opened_by_name = f"{nc.opened_by.prenom} {nc.opened_by.nom}".strip() if nc.opened_by else ""
    assigned_to_name = (
        f"{nc.assigned_to.prenom} {nc.assigned_to.nom}".strip() if nc.assigned_to else None
    )
    closed_by_name = f"{nc.closed_by.prenom} {nc.closed_by.nom}".strip() if nc.closed_by else None

    source_record = nc.source_record
    equipment: Equipement | None = source_record.equipement if source_record else None
    corrective = nc.corrective_action
    photo_url = (
        s3.object_url(corrective.photo_s3_key)
        if s3 and corrective and corrective.photo_s3_key
        else None
    )

    return NonConformityItemResponse(
        id=nc.id,
        workflow_type=nc.workflow_type,
        status=nc.status,
        opened_by_name=opened_by_name,
        opened_at=nc.opened_at,
        assigned_to_name=assigned_to_name,
        assigned_at=nc.assigned_at,
        resolved_at=nc.resolved_at,
        closed_by_name=closed_by_name,
        closed_at=nc.closed_at,
        closing_comment=nc.closing_comment,
        source_record_id=nc.source_record_id,
        equipment_id=equipment.id if equipment else None,
        equipment_name=equipment.nom if equipment else None,
        measured_value=source_record.valeur_mesuree if source_record else None,
        temperature_min=equipment.temperature_min_cible if equipment else None,
        temperature_max=equipment.temperature_max_cible if equipment else None,
        deviation_celsius=(
            _deviation_celsius(
                source_record.valeur_mesuree,
                equipment.temperature_min_cible,
                equipment.temperature_max_cible,
            )
            if source_record and equipment
            else None
        ),
        source=source_record.source if source_record else None,
        corrective_action_id=corrective.id if corrective else None,
        corrective_action_description=corrective.description if corrective else None,
        corrective_action_signed_at=corrective.signee_at if corrective else None,
        corrective_action_photo_url=photo_url,
    )


async def open_temperature_nonconformity(
    releve: ReleveTemperature, db: AsyncSession
) -> NonConformity:
    """Create an OPEN non-conformity linked to an out-of-range temperature record.

    Called from within the HACCP service's ``create_temperature_record``
    transaction.  Uses ``flush`` (not ``commit``) so that the NC ID is
    available for the temperature response without ending the outer transaction.

    Args:
        releve (ReleveTemperature): The out-of-range temperature record that
            triggered this NC. Must already be flushed so its PK is set.
        db (AsyncSession): The async database session.

    Returns:
        NonConformity: The newly flushed (not yet committed) NC instance.
    """
    nc = NonConformity(
        establishment_id=releve.etablissement_id,
        workflow_type=WorkflowType.TEMPERATURE,
        status=NonConformityStatus.OPEN,
        source_record_id=releve.id,
        opened_by_id=releve.utilisateur_id,
        opened_at=releve.mesure_effectuee_at,
    )
    db.add(nc)
    await db.flush()
    NONCONFORMITIES_OPENED_TOTAL.labels(workflow_type=WorkflowType.TEMPERATURE).inc()
    logger.info(
        "nonconformity_opened",
        workflow_type="TEMPERATURE",
        source_record_id=str(releve.id),
    )
    return nc


async def open_manual_temperature_nonconformity(
    db: AsyncSession,
    *,
    establishment_id: UUID,
    opened_by_id: UUID,
    opened_at: datetime,
    reason: str,
) -> NonConformity:
    """Create an OPEN temperature NC without a linked ``ReleveTemperature`` record.

    Used by production HACCP checks (cuisson, refroidissement) where the
    triggering event is a ``ProductionStep`` rather than an equipment reading.
    """
    nc = NonConformity(
        establishment_id=establishment_id,
        workflow_type=WorkflowType.TEMPERATURE,
        status=NonConformityStatus.OPEN,
        source_record_id=None,
        opened_by_id=opened_by_id,
        opened_at=opened_at,
    )
    db.add(nc)
    await db.flush()
    NONCONFORMITIES_OPENED_TOTAL.labels(workflow_type=WorkflowType.TEMPERATURE).inc()
    logger.info(
        "nonconformity_opened",
        workflow_type="TEMPERATURE",
        reason=reason,
        source="manual",
    )
    return nc


async def list_nonconformities(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    status_filter: NonConformityStatus | None = None,
    type_filter: WorkflowType | None = None,
    limit: int = 100,
    s3: S3Service | None = None,
) -> NonConformityListResponse:
    """Return a filtered list of non-conformities with establishment-wide status counts.

    The items query respects ``status_filter``, ``type_filter``, and ``limit``.
    The counts query always covers all NCs in the establishment regardless of
    filters, to keep the dashboard summary bar accurate.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        status_filter (NonConformityStatus | None): Optional status filter.
        type_filter (WorkflowType | None): Optional workflow type filter.
        limit (int): Maximum number of items to return. Defaults to 100.
        s3 (S3Service | None): S3 service for photo URL generation.

    Returns:
        NonConformityListResponse: Filtered items with establishment-wide counts.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)

    where = [NonConformity.establishment_id == establishment.etablissement_id]
    if status_filter is not None:
        where.append(NonConformity.status == status_filter)
    if type_filter is not None:
        where.append(NonConformity.workflow_type == type_filter)

    rows_result = await db.execute(
        select(NonConformity).where(*where).order_by(NonConformity.opened_at.desc()).limit(limit)
    )
    rows = rows_result.scalars().all()

    counts_result = await db.execute(
        select(NonConformity.status, func.count(NonConformity.id))
        .where(NonConformity.establishment_id == establishment.etablissement_id)
        .group_by(NonConformity.status)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in counts_result.all()}

    return NonConformityListResponse(
        items=[_build_item(nc, s3) for nc in rows],
        total_open=counts.get(NonConformityStatus.OPEN, 0),
        total_in_progress=counts.get(NonConformityStatus.IN_PROGRESS, 0),
        total_resolved=counts.get(NonConformityStatus.RESOLVED, 0),
        total_closed=counts.get(NonConformityStatus.CLOSED, 0),
    )


async def get_nonconformity_stats(
    db: AsyncSession, establishment: CurrentEstablishment
) -> NonConformityStatsResponse:
    """Return lightweight status counts for the NC dashboard widget.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        NonConformityStatsResponse: Counts by status and timestamp of the latest NC.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)

    counts_result = await db.execute(
        select(NonConformity.status, func.count(NonConformity.id))
        .where(NonConformity.establishment_id == establishment.etablissement_id)
        .group_by(NonConformity.status)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in counts_result.all()}
    latest_at = (
        await db.execute(
            select(func.max(NonConformity.opened_at)).where(
                NonConformity.establishment_id == establishment.etablissement_id
            )
        )
    ).scalar_one_or_none()

    total_open = counts.get(NonConformityStatus.OPEN, 0)
    total_in_progress = counts.get(NonConformityStatus.IN_PROGRESS, 0)
    total_resolved = counts.get(NonConformityStatus.RESOLVED, 0)
    total_closed = counts.get(NonConformityStatus.CLOSED, 0)

    return NonConformityStatsResponse(
        total=total_open + total_in_progress + total_resolved + total_closed,
        total_open=total_open,
        total_in_progress=total_in_progress,
        total_resolved=total_resolved,
        total_closed=total_closed,
        latest_at=latest_at,
    )


async def _load_nonconformity(
    nonconformity_id: UUID, db: AsyncSession, establishment: CurrentEstablishment
) -> NonConformity:
    """Load a non-conformity scoped to the current establishment.

    Args:
        nonconformity_id (UUID): The NC ticket's primary key.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        NonConformity: The matching NC ORM instance with all relationships loaded.

    Raises:
        HTTPException: 404 Not Found if the NC does not exist or belongs to a
            different establishment.
    """
    result = await db.execute(
        select(NonConformity).where(
            NonConformity.id == nonconformity_id,
            NonConformity.establishment_id == establishment.etablissement_id,
        )
    )
    nc = result.scalar_one_or_none()
    if nc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Non-conformity not found for this establishment.",
        )
    return nc


async def acknowledge_nonconformity(
    nonconformity_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
    s3: S3Service | None = None,
) -> NonConformityItemResponse:
    """Transition a non-conformity from OPEN to IN_PROGRESS.

    Records the acknowledging operator and the acknowledgement timestamp.

    Args:
        nonconformity_id (UUID): The NC to acknowledge.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The operator acknowledging the NC.
        s3 (S3Service | None): S3 service for photo URL generation.

    Returns:
        NonConformityItemResponse: The updated NC detail view.

    Raises:
        HTTPException: 404 Not Found if the NC is not in scope.
        HTTPException: 409 Conflict if the NC is not in OPEN status.
    """
    nc = await _load_nonconformity(nonconformity_id, db, establishment)
    if nc.status != NonConformityStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot acknowledge a non-conformity with status '{nc.status}'.",
        )
    nc.status = NonConformityStatus.IN_PROGRESS
    nc.assigned_to_id = operator.id
    nc.assigned_at = now_for_site(establishment.timezone)
    await db.commit()
    await db.refresh(nc)
    return _build_item(nc, s3)


async def create_corrective_action(
    nonconformity_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
    s3_service: S3Service,
    description: str,
    photo: UploadFile | None = None,
) -> ActionCorrectiveResponse:
    """Submit a corrective action and transition the NC from IN_PROGRESS to RESOLVED.

    Only the S3 object key is stored — never a presigned URL — so that the
    URL remains valid indefinitely and access control stays under application
    control.  A unique constraint on ``nonconformity_id`` prevents duplicate
    corrective actions.

    Args:
        nonconformity_id (UUID): The NC to resolve.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The operator submitting the corrective action.
        s3_service (S3Service): S3 service for photo upload and URL generation.
        description (str): Free-text description of the corrective action taken.
        photo (UploadFile | None): Optional photographic evidence.

    Returns:
        ActionCorrectiveResponse: The created corrective action with photo URL.

    Raises:
        HTTPException: 404 Not Found if the NC is not in scope.
        HTTPException: 409 Conflict if the NC is not IN_PROGRESS or already
            has a corrective action.
        HTTPException: 422 Unprocessable Entity if the description is blank.
    """
    nc = await _load_nonconformity(nonconformity_id, db, establishment)
    if nc.status != NonConformityStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"NC in status '{nc.status}': acknowledge before adding a corrective action.",
        )
    description = description.strip()
    if not description:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Corrective action description is required.",
        )
    if nc.corrective_action is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A corrective action already exists for this non-conformity.",
        )

    photo_s3_key: str | None = None
    if photo is not None:
        # Store only the S3 key — the public URL is generated at read time so
        # it remains valid even if the public endpoint URL is reconfigured.
        photo_s3_key = await s3_service.upload_image(
            photo, prefix=f"haccp/{establishment.etablissement_id}/corrective-actions"
        )

    action = ActionCorrective(
        nonconformity_id=nc.id,
        utilisateur_id=operator.id,
        description=description,
        photo_s3_key=photo_s3_key,
        signee_at=now_for_site(establishment.timezone),
    )
    db.add(action)
    nc.status = NonConformityStatus.RESOLVED
    nc.resolved_at = action.signee_at
    await db.commit()
    await db.refresh(action)

    NONCONFORMITIES_RESOLVED_TOTAL.labels(workflow_type=str(nc.workflow_type)).inc()
    resolution_seconds = (action.signee_at - nc.opened_at).total_seconds()
    NONCONFORMITY_RESOLUTION_SECONDS.labels(workflow_type=str(nc.workflow_type)).observe(
        resolution_seconds
    )
    logger.info(
        "nonconformity_resolved",
        nonconformity_id=str(nc.id),
        workflow_type=str(nc.workflow_type),
        resolution_seconds=round(resolution_seconds, 1),
        has_photo=photo_s3_key is not None,
    )

    return ActionCorrectiveResponse(
        id=action.id,
        releve_id=nc.source_record_id,
        utilisateur_id=action.utilisateur_id,
        description=action.description,
        photo_s3_key=action.photo_s3_key,
        photo_url=s3_service.object_url(action.photo_s3_key) if action.photo_s3_key else None,
        signee_at=action.signee_at,
    )


async def close_nonconformity(
    nonconformity_id: UUID,
    payload: CloseNonConformityRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    s3: S3Service | None = None,
) -> NonConformityItemResponse:
    """Transition a non-conformity from RESOLVED to CLOSED (manager sign-off).

    Only managers (``ensure_admin_org_access``) can close an NC to enforce
    the four-eyes principle: the operator resolves, the manager validates.

    Args:
        nonconformity_id (UUID): The NC to close.
        payload (CloseNonConformityRequest): Optional manager closing comment.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        s3 (S3Service | None): S3 service for photo URL generation.

    Returns:
        NonConformityItemResponse: The closed NC detail view.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the NC is not in scope.
        HTTPException: 409 Conflict if the NC is not in RESOLVED status.
    """
    await ensure_admin_org_access(db, establishment)
    nc = await _load_nonconformity(nonconformity_id, db, establishment)
    if nc.status != NonConformityStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot close a non-conformity with status '{nc.status}'.",
        )
    nc.status = NonConformityStatus.CLOSED
    nc.closed_by_id = establishment.manager_user_id
    nc.closed_at = now_for_site(establishment.timezone)
    nc.closing_comment = payload.closing_comment
    await db.commit()
    await db.refresh(nc)
    NONCONFORMITIES_CLOSED_TOTAL.inc()
    logger.info(
        "nonconformity_closed",
        nonconformity_id=str(nc.id),
        workflow_type=str(nc.workflow_type),
    )
    return _build_item(nc, s3)
