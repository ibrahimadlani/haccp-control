"""Integration tests for app/modules/nonconformities/service.py."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.haccp.models import SourceReleve, TypeEvenementPointage
from app.modules.haccp.schemas import TemperatureRecordCreate
from app.modules.haccp.service import create_temperature_record
from app.modules.nonconformities.models import NonConformity, NonConformityStatus, WorkflowType
from app.modules.nonconformities.schemas import CloseNonConformityRequest
from app.modules.nonconformities.service import (
    acknowledge_nonconformity,
    close_nonconformity,
    create_corrective_action,
    get_nonconformity_stats,
    list_nonconformities,
)
from tests.integration.conftest import (
    make_base_seed,
    make_equipment,
    make_establishment,
    make_establishment_ctx,
    make_organisation,
    make_role,
    make_user,
)


async def _open_nc(test_db, seed, equip) -> NonConformity:
    """Helper: create a temperature NC by recording out-of-range temperature."""
    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("99.0"),  # always out of range
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    from sqlalchemy import select
    nc = (await test_db.execute(
        select(NonConformity).where(NonConformity.id == result.nonconformity_id)
    )).scalar_one()
    return nc


# ── Full lifecycle ────────────────────────────────────────────────────────────


async def test_nc_lifecycle_open_to_closed(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    assert nc.status == NonConformityStatus.OPEN

    # Acknowledge
    await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)
    await test_db.refresh(nc)
    assert nc.status == NonConformityStatus.IN_PROGRESS
    assert nc.assigned_to_id == seed.operator.id

    # Corrective action (mock S3)
    mock_s3 = MagicMock()
    mock_s3.upload_image = AsyncMock(return_value="haccp/test/photo.jpg")
    mock_s3.object_url = MagicMock(return_value="http://s3.local/photo.jpg")

    await create_corrective_action(
        nc.id, test_db, seed.ctx, seed.operator, mock_s3, "Réglage du frigo"
    )
    await test_db.refresh(nc)
    assert nc.status == NonConformityStatus.RESOLVED
    assert nc.resolved_at is not None

    # Close (manager)
    await close_nonconformity(
        nc.id,
        CloseNonConformityRequest(closing_comment="OK"),
        test_db,
        seed.ctx,
    )
    await test_db.refresh(nc)
    assert nc.status == NonConformityStatus.CLOSED
    assert nc.closed_at is not None
    assert nc.closing_comment == "OK"


# ── Invalid transitions ───────────────────────────────────────────────────────


async def test_acknowledge_already_in_progress_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)

    with pytest.raises(HTTPException) as exc_info:
        await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 409


async def test_corrective_action_on_open_nc_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    mock_s3 = MagicMock()
    mock_s3.upload_image = AsyncMock(return_value=None)
    mock_s3.object_url = MagicMock(return_value="http://s3.local/x")

    with pytest.raises(HTTPException) as exc_info:
        await create_corrective_action(
            nc.id, test_db, seed.ctx, seed.operator, mock_s3, "Action"
        )
    assert exc_info.value.status_code == 409


async def test_close_nc_not_resolved_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    with pytest.raises(HTTPException) as exc_info:
        await close_nonconformity(
            nc.id, CloseNonConformityRequest(), test_db, seed.ctx
        )
    assert exc_info.value.status_code == 409


async def test_corrective_action_blank_description_raises_422(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)
    await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)

    mock_s3 = MagicMock()
    mock_s3.upload_image = AsyncMock(return_value=None)
    mock_s3.object_url = MagicMock(return_value="")

    with pytest.raises(HTTPException) as exc_info:
        await create_corrective_action(nc.id, test_db, seed.ctx, seed.operator, mock_s3, "   ")
    assert exc_info.value.status_code == 422


# ── Permission gating ─────────────────────────────────────────────────────────


async def test_close_nc_by_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    # Build an operator-level context (non-manager)
    non_manager_ctx = make_establishment_ctx(
        seed.org, seed.est, seed.operator,  # operator as manager_user_id
        is_org_admin=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await close_nonconformity(
            nc.id, CloseNonConformityRequest(), test_db, non_manager_ctx
        )
    assert exc_info.value.status_code == 403


async def test_list_nonconformities_by_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(
        seed.org, seed.est, seed.operator, is_org_admin=False
    )
    with pytest.raises(HTTPException) as exc_info:
        await list_nonconformities(test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


# ── List and stats ────────────────────────────────────────────────────────────


async def test_list_nonconformities_returns_all(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    await _open_nc(test_db, seed, equip)
    await _open_nc(test_db, seed, equip)

    response = await list_nonconformities(test_db, seed.ctx)
    assert len(response.items) == 2
    assert response.total_open == 2


async def test_list_nonconformities_status_filter(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)
    await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)
    await _open_nc(test_db, seed, equip)  # second one stays OPEN

    response = await list_nonconformities(
        test_db, seed.ctx, status_filter=NonConformityStatus.IN_PROGRESS
    )
    assert len(response.items) == 1


async def test_get_nonconformity_stats_empty(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    stats = await get_nonconformity_stats(test_db, seed.ctx)
    assert stats.total == 0
    assert stats.total_open == 0
    assert stats.latest_at is None


async def test_get_nonconformity_stats_with_data(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    await _open_nc(test_db, seed, equip)

    stats = await get_nonconformity_stats(test_db, seed.ctx)
    assert stats.total == 1
    assert stats.total_open == 1
    assert stats.latest_at is not None
