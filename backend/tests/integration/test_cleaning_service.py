"""Integration tests for app/modules/cleaning/service.py."""

import uuid
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cleaning.models import CleaningStatus, ScheduleType
from app.modules.cleaning.schemas import (
    BulkCleaningLogCreate,
    CleaningLogItem,
    CleaningRoutineCreate,
    CleaningTaskTemplateCreate,
    CleaningZoneCreate,
)
from app.modules.cleaning.service import (
    bulk_create_logs,
    create_routine,
    create_task_template,
    create_zone,
    delete_zone,
    get_current_routine,
    get_routine_detail,
    list_zones,
)
from tests.integration.conftest import (
    make_base_seed,
    make_cleaning_routine,
    make_cleaning_task,
    make_cleaning_zone,
)

# ── Zone CRUD ────────────────────────────────────────────────────────────────


async def test_create_zone(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = CleaningZoneCreate(name="Cuisine chaude")
    result = await create_zone(payload, test_db, seed.ctx)
    assert result.name == "Cuisine chaude"
    assert result.id is not None


async def test_list_zones_returns_created(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await make_cleaning_zone(test_db, seed.est, name="Zone A")
    await make_cleaning_zone(test_db, seed.est, name="Zone B")

    response = await list_zones(test_db, seed.ctx)
    names = {z.name for z in response.items}
    assert "Zone A" in names
    assert "Zone B" in names


async def test_delete_zone(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    zone = await make_cleaning_zone(test_db, seed.est)

    await delete_zone(zone.id, test_db, seed.ctx)
    response = await list_zones(test_db, seed.ctx)
    assert zone.id not in {z.id for z in response.items}


# ── Routine CRUD ──────────────────────────────────────────────────────────────


async def test_create_routine(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = CleaningRoutineCreate(name="Ouverture cuisine", schedule_type=ScheduleType.OPENING)
    result = await create_routine(payload, test_db, seed.ctx)
    assert result.name == "Ouverture cuisine"
    assert result.schedule_type == ScheduleType.OPENING


async def test_create_task_template(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    zone = await make_cleaning_zone(test_db, seed.est)
    routine = await make_cleaning_routine(test_db, seed.est)

    payload = CleaningTaskTemplateCreate(
        zone_id=zone.id,
        name="Nettoyer la plancha",
    )
    result = await create_task_template(routine.id, payload, test_db, seed.ctx)
    assert result.name == "Nettoyer la plancha"


# ── Schedule inference ────────────────────────────────────────────────────────


async def test_get_current_routine_returns_opening_in_the_morning(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    opening = await make_cleaning_routine(
        test_db, seed.est, schedule_type=ScheduleType.OPENING, name="Opening"
    )
    await make_cleaning_routine(
        test_db, seed.est, schedule_type=ScheduleType.CLOSING, name="Closing"
    )

    morning = datetime(2024, 6, 1, 9, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=morning):
        result = await get_current_routine(test_db, seed.ctx)
    assert result.routine_id == opening.id


async def test_get_current_routine_returns_closing_in_afternoon(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await make_cleaning_routine(test_db, seed.est, schedule_type=ScheduleType.OPENING)
    closing = await make_cleaning_routine(test_db, seed.est, schedule_type=ScheduleType.CLOSING)

    afternoon = datetime(2024, 6, 1, 14, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=afternoon):
        result = await get_current_routine(test_db, seed.ctx)
    assert result.routine_id == closing.id


async def test_get_current_routine_fallback_when_no_matching_schedule(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    # Only an OPENING routine exists
    routine = await make_cleaning_routine(test_db, seed.est, schedule_type=ScheduleType.OPENING)

    # Request at afternoon (expects CLOSING, but only OPENING exists → fallback)
    afternoon = datetime(2024, 6, 1, 15, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=afternoon):
        result = await get_current_routine(test_db, seed.ctx)
    assert result.routine_id == routine.id


# ── Bulk logs ─────────────────────────────────────────────────────────────────


async def test_bulk_create_logs_all_valid(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    zone = await make_cleaning_zone(test_db, seed.est)
    routine = await make_cleaning_routine(test_db, seed.est)
    task = await make_cleaning_task(test_db, routine, zone)

    payload = BulkCleaningLogCreate(
        items=[CleaningLogItem(task_id=task.id, status=CleaningStatus.DONE)]
    )
    result = await bulk_create_logs(payload, test_db, seed.ctx, seed.operator)
    assert len(result.created) == 1


async def test_bulk_create_logs_unknown_task_id_raises_400(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    payload = BulkCleaningLogCreate(
        items=[CleaningLogItem(task_id=uuid.uuid4(), status=CleaningStatus.DONE)]
    )
    with pytest.raises(HTTPException) as exc_info:
        await bulk_create_logs(payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 400


# ── Routine detail ─────────────────────────────────────────────────────────────


async def test_get_routine_detail_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await get_routine_detail(uuid.uuid4(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_get_routine_detail_includes_tasks(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    zone = await make_cleaning_zone(test_db, seed.est)
    routine = await make_cleaning_routine(test_db, seed.est)
    await make_cleaning_task(test_db, routine, zone, name="Tâche A")
    await make_cleaning_task(test_db, routine, zone, name="Tâche B")

    detail = await get_routine_detail(routine.id, test_db, seed.ctx)
    # RoutineTodoResponse groups tasks by zone — collect all task names across zones
    task_names = {t.name for zone_item in detail.zones for t in zone_item.tasks}
    assert "Tâche A" in task_names
    assert "Tâche B" in task_names


async def test_bulk_create_logs_mixed_statuses(test_db: AsyncSession):
    """DONE and ISSUE statuses must both be accepted and stored."""
    from app.modules.cleaning.models import CleaningStatus

    seed = await make_base_seed(test_db)
    zone = await make_cleaning_zone(test_db, seed.est)
    routine = await make_cleaning_routine(test_db, seed.est)
    task_done = await make_cleaning_task(test_db, routine, zone, name="T-DONE")
    task_issue = await make_cleaning_task(test_db, routine, zone, name="T-ISSUE")

    payload = BulkCleaningLogCreate(
        items=[
            CleaningLogItem(task_id=task_done.id, status=CleaningStatus.DONE),
            CleaningLogItem(
                task_id=task_issue.id,
                status=CleaningStatus.ISSUE,
                comment="Mousse insuffisante",
            ),
        ]
    )
    result = await bulk_create_logs(payload, test_db, seed.ctx, seed.operator)
    assert len(result.created) == 2
    statuses = {log.status for log in result.created}
    assert CleaningStatus.DONE in statuses
    assert CleaningStatus.ISSUE in statuses


async def test_get_current_routine_no_routines_raises_404(test_db: AsyncSession):
    """No routines configured must raise 404, not a server error."""
    seed = await make_base_seed(test_db)
    morning = datetime(2024, 6, 1, 9, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=morning):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_routine(test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_create_zone_scoped_to_establishment(test_db: AsyncSession):
    """Zones from one establishment must not appear in another's list."""
    from tests.integration.conftest import (
        make_establishment,
        make_establishment_ctx,
        make_organisation,
        make_role,
        make_user,
    )

    seed = await make_base_seed(test_db)
    other_org = await make_organisation(test_db)
    other_est = await make_establishment(test_db, other_org)
    other_role = await make_role(test_db)
    other_user = await make_user(test_db, other_org, other_est, other_role)
    other_ctx = make_establishment_ctx(other_org, other_est, other_user)

    await create_zone(
        CleaningZoneCreate(name="Zone privée autre établissement"), test_db, other_ctx
    )
    await create_zone(CleaningZoneCreate(name="Zone propre"), test_db, seed.ctx)

    response = await list_zones(test_db, seed.ctx)
    names = {z.name for z in response.items}
    assert "Zone privée autre établissement" not in names
    assert "Zone propre" in names
