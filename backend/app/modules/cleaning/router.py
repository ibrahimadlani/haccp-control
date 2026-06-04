"""
FastAPI router for the Cleaning (Nettoyage) domain.

Exposes endpoints for managing the cleaning plan and recording execution logs:

**Configuration** (manager-facing):
- ``GET/POST /cleaning-zones`` — list and create cleaning zones.
- ``DELETE  /cleaning-zones/{zone_id}``
- ``GET/POST /cleaning-routines`` — list and create cleaning routines.
- ``DELETE  /cleaning-routines/{routine_id}``
- ``POST    /cleaning-routines/{routine_id}/tasks`` — add a task template.
- ``DELETE  /cleaning-tasks/{task_id}``

**Execution** (tablet operator-facing):
- ``GET  /cleaning-routines/current`` — auto-select and return today's routine.
- ``GET  /cleaning-routines/{routine_id}`` — load a specific routine with task status.
- ``POST /cleaning-logs/bulk`` — submit multiple task completions in one call.

All endpoints require an establishment JWT (``CurrentSite``).  Bulk log
creation additionally requires ``CurrentOperator`` (PIN authentication).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.modules.cleaning import service
from app.modules.cleaning.models import ScheduleType
from app.modules.cleaning.schemas import (
    BulkCleaningLogCreate,
    BulkCleaningLogResponse,
    CleaningRoutineCreate,
    CleaningRoutineListResponse,
    CleaningRoutineResponse,
    CleaningTaskTemplateCreate,
    CleaningTaskTemplateResponse,
    CleaningZoneCreate,
    CleaningZoneListResponse,
    CleaningZoneResponse,
    RoutineTodoResponse,
)

router = APIRouter(tags=["Nettoyage"], dependencies=[Depends(require_feature(Feature.CLEANING))])


@router.get("/cleaning-zones", response_model=CleaningZoneListResponse)
async def list_cleaning_zones(
    db: DatabaseSession, establishment: CurrentSite
) -> CleaningZoneListResponse:
    """List all cleaning zones for the current establishment.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        CleaningZoneListResponse: Zones sorted by name.
    """
    return await service.list_zones(db, establishment)


@router.post("/cleaning-zones", response_model=CleaningZoneResponse, status_code=201)
async def create_cleaning_zone(
    payload: CleaningZoneCreate, db: DatabaseSession, establishment: CurrentSite
) -> CleaningZoneResponse:
    """Create a new cleaning zone.

    Args:
        payload (CleaningZoneCreate): Zone name.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        CleaningZoneResponse: The created zone.
    """
    return await service.create_zone(payload, db, establishment)


@router.delete("/cleaning-zones/{zone_id}", status_code=204)
async def delete_cleaning_zone(
    zone_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> None:
    """Delete a cleaning zone.

    Will fail if task templates still reference this zone (RESTRICT FK).

    Args:
        zone_id (UUID): The zone to delete.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.delete_zone(zone_id, db, establishment)


@router.get("/cleaning-routines", response_model=CleaningRoutineListResponse)
async def list_cleaning_routines(
    db: DatabaseSession, establishment: CurrentSite
) -> CleaningRoutineListResponse:
    """List all cleaning routines for the current establishment.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        CleaningRoutineListResponse: Routines sorted by name.
    """
    return await service.list_routines(db, establishment)


@router.post("/cleaning-routines", response_model=CleaningRoutineResponse, status_code=201)
async def create_cleaning_routine(
    payload: CleaningRoutineCreate, db: DatabaseSession, establishment: CurrentSite
) -> CleaningRoutineResponse:
    """Create a new cleaning routine.

    Args:
        payload (CleaningRoutineCreate): Routine name and schedule type.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        CleaningRoutineResponse: The created routine.
    """
    return await service.create_routine(payload, db, establishment)


@router.get("/cleaning-routines/current", response_model=RoutineTodoResponse)
async def get_current_routine(
    db: DatabaseSession,
    establishment: CurrentSite,
    schedule_type: Annotated[ScheduleType | None, Query()] = None,
) -> RoutineTodoResponse:
    """Return the todo-list for today's auto-selected or explicitly requested routine.

    When ``schedule_type`` is omitted, the routine is selected based on the
    current site-local hour (OPENING before 13:00, CLOSING otherwise).

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        schedule_type (ScheduleType | None): Optional schedule override.

    Returns:
        RoutineTodoResponse: The selected routine's todo view with today's logs.

    Raises:
        HTTPException: 404 if no routine is configured for this establishment.
    """
    return await service.get_current_routine(db, establishment, schedule_type)


@router.get("/cleaning-routines/{routine_id}", response_model=RoutineTodoResponse)
async def get_cleaning_routine(
    routine_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> RoutineTodoResponse:
    """Return the todo-list view for a specific routine.

    Args:
        routine_id (UUID): The routine to load.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        RoutineTodoResponse: Routine with zones, tasks, and today's logs.
    """
    return await service.get_routine_detail(routine_id, db, establishment)


@router.delete("/cleaning-routines/{routine_id}", status_code=204)
async def delete_cleaning_routine(
    routine_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> None:
    """Delete a cleaning routine and all its task templates.

    Args:
        routine_id (UUID): The routine to delete.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.delete_routine(routine_id, db, establishment)


@router.post(
    "/cleaning-routines/{routine_id}/tasks",
    response_model=CleaningTaskTemplateResponse,
    status_code=201,
)
async def create_task_template(
    routine_id: UUID,
    payload: CleaningTaskTemplateCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> CleaningTaskTemplateResponse:
    """Add a task template to a cleaning routine.

    Args:
        routine_id (UUID): The target routine.
        payload (CleaningTaskTemplateCreate): Task name, zone, and description.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        CleaningTaskTemplateResponse: The created task template.
    """
    return await service.create_task_template(routine_id, payload, db, establishment)


@router.delete("/cleaning-tasks/{task_id}", status_code=204)
async def delete_task_template(
    task_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> None:
    """Delete a cleaning task template.

    Args:
        task_id (UUID): The task template to delete.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.delete_task_template(task_id, db, establishment)


@router.post("/cleaning-logs/bulk", response_model=BulkCleaningLogResponse, status_code=201)
async def bulk_create_cleaning_logs(
    payload: BulkCleaningLogCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> BulkCleaningLogResponse:
    """Submit multiple cleaning task completions in a single request.

    Validates all task IDs before writing any logs, so the batch either
    fully succeeds or fully fails.

    Args:
        payload (BulkCleaningLogCreate): List of task completions.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        BulkCleaningLogResponse: Created log entries and count.
    """
    return await service.bulk_create_logs(payload, db, establishment, operator)
