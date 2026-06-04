"""
Business logic for the Cleaning (Nettoyage) domain.

Provides CRUD operations for the cleaning plan configuration and the
execution log workflow:

**Configuration** — ``list_zones``, ``create_zone``, ``delete_zone``,
``list_routines``, ``create_routine``, ``delete_routine``,
``create_task_template``, ``delete_task_template``.

**Execution** — ``get_routine_detail`` and ``get_current_routine`` return
the full routine todo-list view (tasks + today's logs).
``get_current_routine`` automatically infers the appropriate
``ScheduleType`` (OPENING before 13:00, CLOSING otherwise) and falls back
to the oldest routine if no matching schedule is found.

``bulk_create_logs`` processes a whole routine submission in a single
transaction using a savepoint (``begin_nested``), so that a partial failure
does not leave the log in an inconsistent state.

Private helpers ``_get_zone``, ``_get_routine``, and ``_get_task`` provide
consistent 404-raising tenant-scoped lookups used throughout this module.
"""

from collections import defaultdict
from datetime import date
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.metrics import CLEANING_LOGS_TOTAL
from app.core.time_utils import now_for_site
from app.modules.cleaning.models import (
    CleaningLog,
    CleaningRoutine,
    CleaningTaskTemplate,
    CleaningZone,
    ScheduleType,
)
from app.modules.cleaning.schemas import (
    BulkCleaningLogCreate,
    BulkCleaningLogResponse,
    CleaningLogResponse,
    CleaningRoutineCreate,
    CleaningRoutineListResponse,
    CleaningRoutineResponse,
    CleaningTaskTemplateCreate,
    CleaningTaskTemplateResponse,
    CleaningZoneCreate,
    CleaningZoneListResponse,
    CleaningZoneResponse,
    RoutineTodoResponse,
    TaskTodoItem,
    ZoneTodoItem,
)
from app.modules.personnel.models import Utilisateur

logger = structlog.get_logger(__name__)


async def list_zones(
    db: AsyncSession, establishment: CurrentEstablishment
) -> CleaningZoneListResponse:
    """Return all cleaning zones for the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        CleaningZoneListResponse: Zones sorted alphabetically by name.
    """
    result = await db.execute(
        select(CleaningZone)
        .where(CleaningZone.establishment_id == establishment.etablissement_id)
        .order_by(CleaningZone.name)
    )
    return CleaningZoneListResponse(
        items=[CleaningZoneResponse.model_validate(z) for z in result.scalars().all()]
    )


async def create_zone(
    payload: CleaningZoneCreate, db: AsyncSession, establishment: CurrentEstablishment
) -> CleaningZoneResponse:
    """Create a new cleaning zone for the current establishment.

    Args:
        payload (CleaningZoneCreate): Validated zone data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        CleaningZoneResponse: The created zone.
    """
    zone = CleaningZone(establishment_id=establishment.etablissement_id, name=payload.name)
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return CleaningZoneResponse.model_validate(zone)


async def delete_zone(zone_id: UUID, db: AsyncSession, establishment: CurrentEstablishment) -> None:
    """Delete a cleaning zone.

    Will raise a database error if any task templates still reference this
    zone (RESTRICT FK on delete), preventing orphaned templates.

    Args:
        zone_id (UUID): The zone to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the zone is not in scope.
    """
    zone = await _get_zone(db, establishment, zone_id)
    await db.delete(zone)
    await db.commit()


async def list_routines(
    db: AsyncSession, establishment: CurrentEstablishment
) -> CleaningRoutineListResponse:
    """Return all cleaning routines for the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        CleaningRoutineListResponse: Routines sorted alphabetically by name.
    """
    result = await db.execute(
        select(CleaningRoutine)
        .where(CleaningRoutine.establishment_id == establishment.etablissement_id)
        .order_by(CleaningRoutine.name)
    )
    return CleaningRoutineListResponse(
        items=[CleaningRoutineResponse.model_validate(r) for r in result.scalars().all()]
    )


async def create_routine(
    payload: CleaningRoutineCreate, db: AsyncSession, establishment: CurrentEstablishment
) -> CleaningRoutineResponse:
    """Create a new cleaning routine for the current establishment.

    Args:
        payload (CleaningRoutineCreate): Validated routine data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        CleaningRoutineResponse: The created routine.
    """
    routine = CleaningRoutine(
        establishment_id=establishment.etablissement_id,
        name=payload.name,
        schedule_type=payload.schedule_type,
    )
    db.add(routine)
    await db.commit()
    await db.refresh(routine)
    return CleaningRoutineResponse.model_validate(routine)


async def delete_routine(
    routine_id: UUID, db: AsyncSession, establishment: CurrentEstablishment
) -> None:
    """Delete a cleaning routine and all its task templates (CASCADE).

    Args:
        routine_id (UUID): The routine to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the routine is not in scope.
    """
    routine = await _get_routine(db, establishment, routine_id)
    await db.delete(routine)
    await db.commit()


async def create_task_template(
    routine_id: UUID,
    payload: CleaningTaskTemplateCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> CleaningTaskTemplateResponse:
    """Add a task template to a cleaning routine.

    Validates that both the parent routine and the referenced zone belong to
    the current establishment before creating the template.

    Args:
        routine_id (UUID): The target routine.
        payload (CleaningTaskTemplateCreate): Task name, zone, and instructions.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        CleaningTaskTemplateResponse: The created task template.

    Raises:
        HTTPException: 404 Not Found if the routine or zone is not in scope.
    """
    await _get_routine(db, establishment, routine_id)
    await _get_zone(db, establishment, payload.zone_id)
    task = CleaningTaskTemplate(
        routine_id=routine_id,
        zone_id=payload.zone_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return CleaningTaskTemplateResponse.model_validate(task)


async def delete_task_template(
    task_id: UUID, db: AsyncSession, establishment: CurrentEstablishment
) -> None:
    """Delete a cleaning task template.

    Args:
        task_id (UUID): The task template to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the template is not in scope.
    """
    task = await _get_task(db, establishment, task_id)
    await db.delete(task)
    await db.commit()


async def get_routine_detail(
    routine_id: UUID, db: AsyncSession, establishment: CurrentEstablishment
) -> RoutineTodoResponse:
    """Return the full todo-list view for a specific routine.

    Args:
        routine_id (UUID): The routine to load.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        RoutineTodoResponse: The routine with zones, tasks, and today's logs.

    Raises:
        HTTPException: 404 Not Found if the routine is not in scope.
    """
    routine = await _get_routine(db, establishment, routine_id)
    return await _build_routine_todo(routine, db, establishment)


async def get_current_routine(
    db: AsyncSession, establishment: CurrentEstablishment, schedule_type: ScheduleType | None = None
) -> RoutineTodoResponse:
    """Return the todo-list view for the most appropriate routine right now.

    Routine selection logic:
    1. If ``schedule_type`` is provided, use it directly.
    2. Otherwise, infer OPENING (before 13:00) or CLOSING (13:00+) from the
       site-local time.
    3. If no matching routine exists, fall back to the oldest routine in the
       establishment to avoid a confusing 404 on a tablet that has only one
       routine regardless of schedule type.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        schedule_type (ScheduleType | None): Override for automatic inference.

    Returns:
        RoutineTodoResponse: The selected routine's todo-list view.

    Raises:
        HTTPException: 404 Not Found if no routine is configured at all.
    """
    if schedule_type is None:
        schedule_type = _infer_schedule_type(establishment.timezone)

    result = await db.execute(
        select(CleaningRoutine)
        .where(
            CleaningRoutine.establishment_id == establishment.etablissement_id,
            CleaningRoutine.schedule_type == schedule_type,
        )
        .limit(1)
    )
    routine = result.scalar_one_or_none()

    if routine is None:
        # Fallback: return the oldest routine rather than 404 so the tablet
        # always has something to display even if schedule types are not configured.
        fallback = await db.execute(
            select(CleaningRoutine)
            .where(CleaningRoutine.establishment_id == establishment.etablissement_id)
            .order_by(CleaningRoutine.created_at)
            .limit(1)
        )
        routine = fallback.scalar_one_or_none()

    if routine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune routine de nettoyage configurée pour cet établissement.",
        )

    return await _build_routine_todo(routine, db, establishment)


async def bulk_create_logs(
    payload: BulkCleaningLogCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> BulkCleaningLogResponse:
    """Create cleaning log entries for multiple tasks in a single transaction.

    Validates all task IDs belong to a routine in the current establishment
    before writing any rows, so the entire batch succeeds or fails together.

    Uses a savepoint (``begin_nested``) so a mid-batch error rolls back only
    the log writes without affecting outer transaction state.

    Args:
        payload (BulkCleaningLogCreate): List of task completions.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The operator executing the tasks.

    Returns:
        BulkCleaningLogResponse: Created log entries and their count.

    Raises:
        HTTPException: 400 Bad Request if any task IDs are not valid for this
            establishment.
    """
    now = now_for_site(establishment.timezone)
    task_ids = [item.task_id for item in payload.items]

    result = await db.execute(
        select(CleaningTaskTemplate.id)
        .join(CleaningRoutine, CleaningRoutine.id == CleaningTaskTemplate.routine_id)
        .where(
            CleaningTaskTemplate.id.in_(task_ids),
            CleaningRoutine.establishment_id == establishment.etablissement_id,
        )
    )
    valid_ids = {row[0] for row in result.all()}
    unknown = set(task_ids) - valid_ids
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tâche(s) inconnue(s) : {[str(i) for i in unknown]}",
        )

    logs: list[CleaningLog] = []
    async with db.begin_nested():
        for item in payload.items:
            log = CleaningLog(
                establishment_id=establishment.etablissement_id,
                operator_id=operator.id,
                task_id=item.task_id,
                status=item.status,
                comment=item.comment,
                executed_at=now,
            )
            db.add(log)
            logs.append(log)

    await db.commit()
    for log in logs:
        await db.refresh(log)

    for item in payload.items:
        CLEANING_LOGS_TOTAL.labels(status=str(item.status)).inc()
    logger.info(
        "cleaning_logs_bulk_created",
        count=len(logs),
        issue_count=sum(1 for item in payload.items if str(item.status) == "ISSUE"),
    )
    return BulkCleaningLogResponse(
        created=[CleaningLogResponse.model_validate(lg) for lg in logs], count=len(logs)
    )


def _infer_schedule_type(timezone: str) -> ScheduleType:
    """Infer the appropriate schedule type from the current site-local hour.

    Before 13:00 → OPENING; 13:00 or later → CLOSING.

    Args:
        timezone (str): The IANA timezone string of the establishment.

    Returns:
        ScheduleType: The inferred schedule type for the current time of day.
    """
    return ScheduleType.OPENING if now_for_site(timezone).hour < 13 else ScheduleType.CLOSING


async def _build_routine_todo(
    routine: CleaningRoutine, db: AsyncSession, establishment: CurrentEstablishment
) -> RoutineTodoResponse:
    """Build the full todo-list view for a routine, annotating tasks with today's logs.

    Fetches all task templates and today's logs in two queries (not N+1),
    then assembles the nested zone → task → log structure in Python.

    The date comparison uses PostgreSQL's ``AT TIME ZONE`` operator with the
    establishment's timezone to ensure the "today" boundary matches the
    kitchen's local midnight, not UTC midnight.

    Args:
        routine (CleaningRoutine): The ORM routine instance.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        RoutineTodoResponse: The fully assembled todo-list view.
    """
    tmpl_result = await db.execute(
        select(CleaningTaskTemplate)
        .where(CleaningTaskTemplate.routine_id == routine.id)
        .order_by(CleaningTaskTemplate.zone_id, CleaningTaskTemplate.name)
    )
    templates = tmpl_result.scalars().all()
    if not templates:
        return RoutineTodoResponse(
            routine_id=routine.id,
            routine_name=routine.name,
            schedule_type=routine.schedule_type,
            zones=[],
        )

    task_ids = [t.id for t in templates]
    today: date = now_for_site(establishment.timezone).date()

    logs_result = await db.execute(
        select(CleaningLog)
        .where(
            CleaningLog.task_id.in_(task_ids),
            CleaningLog.establishment_id == establishment.etablissement_id,
            # Compare the log's timestamp in the establishment's local timezone
            # so that a session that started just before midnight is shown as
            # today's work, not yesterday's.
            func.date(CleaningLog.executed_at.op("AT TIME ZONE")(establishment.timezone)) == today,
        )
        .order_by(CleaningLog.executed_at.desc())
    )
    latest_log: dict[UUID, CleaningLog] = {}
    for lg in logs_result.scalars().all():
        if lg.task_id not in latest_log:
            latest_log[lg.task_id] = lg

    zone_ids = list({t.zone_id for t in templates})
    zones_result = await db.execute(
        select(CleaningZone).where(CleaningZone.id.in_(zone_ids)).order_by(CleaningZone.name)
    )
    zones_by_id: dict[UUID, CleaningZone] = {z.id: z for z in zones_result.scalars().all()}

    tasks_by_zone: dict[UUID, list[CleaningTaskTemplate]] = defaultdict(list)
    for t in templates:
        tasks_by_zone[t.zone_id].append(t)

    zone_items = []
    for zone_id in sorted(tasks_by_zone, key=lambda zid: zones_by_id[zid].name):
        zone = zones_by_id[zone_id]
        task_items = [
            TaskTodoItem(
                task_id=t.id,
                name=t.name,
                description=t.description,
                log=CleaningLogResponse.model_validate(latest_log[t.id])
                if t.id in latest_log
                else None,
            )
            for t in tasks_by_zone[zone_id]
        ]
        zone_items.append(ZoneTodoItem(zone_id=zone.id, zone_name=zone.name, tasks=task_items))

    return RoutineTodoResponse(
        routine_id=routine.id,
        routine_name=routine.name,
        schedule_type=routine.schedule_type,
        zones=zone_items,
    )


async def _get_zone(
    db: AsyncSession, establishment: CurrentEstablishment, zone_id: UUID
) -> CleaningZone:
    """Load a cleaning zone scoped to the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        zone_id (UUID): The zone's primary key.

    Returns:
        CleaningZone: The matching zone ORM instance.

    Raises:
        HTTPException: 404 Not Found if the zone is not found in this establishment.
    """
    result = await db.execute(
        select(CleaningZone).where(
            CleaningZone.id == zone_id,
            CleaningZone.establishment_id == establishment.etablissement_id,
        )
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone introuvable.")
    return zone


async def _get_routine(
    db: AsyncSession, establishment: CurrentEstablishment, routine_id: UUID
) -> CleaningRoutine:
    """Load a cleaning routine scoped to the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        routine_id (UUID): The routine's primary key.

    Returns:
        CleaningRoutine: The matching routine ORM instance.

    Raises:
        HTTPException: 404 Not Found if the routine is not in scope.
    """
    result = await db.execute(
        select(CleaningRoutine).where(
            CleaningRoutine.id == routine_id,
            CleaningRoutine.establishment_id == establishment.etablissement_id,
        )
    )
    routine = result.scalar_one_or_none()
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine introuvable.")
    return routine


async def _get_task(
    db: AsyncSession, establishment: CurrentEstablishment, task_id: UUID
) -> CleaningTaskTemplate:
    """Load a task template scoped to the current establishment via its parent routine.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        task_id (UUID): The task template's primary key.

    Returns:
        CleaningTaskTemplate: The matching task template ORM instance.

    Raises:
        HTTPException: 404 Not Found if the task is not in scope.
    """
    result = await db.execute(
        select(CleaningTaskTemplate)
        .join(CleaningRoutine, CleaningRoutine.id == CleaningTaskTemplate.routine_id)
        .where(
            CleaningTaskTemplate.id == task_id,
            CleaningRoutine.establishment_id == establishment.etablissement_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    return task
