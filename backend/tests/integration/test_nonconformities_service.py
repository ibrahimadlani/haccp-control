"""Integration tests for app/modules/nonconformities/service.py."""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.haccp.schemas import TemperatureRecordCreate
from app.modules.haccp.service import create_temperature_record
from app.modules.nonconformities.models import NonConformity, NonConformityStatus
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
    make_establishment_ctx,
)


async def _open_nc(test_db, seed, equip) -> NonConformity:
    """Helper: create a temperature NC by recording out-of-range temperature."""
    payload = TemperatureRecordCreate(
        equipment_id=equip.id,
        measured_value=Decimal("99.0"),  # always out of range
    )
    result = await create_temperature_record(payload, test_db, seed.ctx, seed.operator)
    from sqlalchemy import select

    nc = (
        await test_db.execute(
            select(NonConformity).where(NonConformity.id == result.nonconformity_id)
        )
    ).scalar_one()
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
        await create_corrective_action(nc.id, test_db, seed.ctx, seed.operator, mock_s3, "Action")
    assert exc_info.value.status_code == 409


async def test_close_nc_not_resolved_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)

    with pytest.raises(HTTPException) as exc_info:
        await close_nonconformity(nc.id, CloseNonConformityRequest(), test_db, seed.ctx)
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
        seed.org,
        seed.est,
        seed.operator,  # operator as manager_user_id
        is_org_admin=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await close_nonconformity(nc.id, CloseNonConformityRequest(), test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


async def test_list_nonconformities_by_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
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


async def test_corrective_action_already_exists_raises_409(test_db: AsyncSession):
    """A second corrective action on the same NC must raise 409."""
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    nc = await _open_nc(test_db, seed, equip)
    await acknowledge_nonconformity(nc.id, test_db, seed.ctx, seed.operator)

    mock_s3 = MagicMock()
    mock_s3.upload_image = AsyncMock(return_value=None)
    mock_s3.object_url = MagicMock(return_value="http://s3.local/photo.jpg")

    await create_corrective_action(
        nc.id, test_db, seed.ctx, seed.operator, mock_s3, "Première action"
    )

    # NC is now RESOLVED; trying to add another must fail
    with pytest.raises(HTTPException) as exc_info:
        await create_corrective_action(
            nc.id, test_db, seed.ctx, seed.operator, mock_s3, "Deuxième action"
        )
    assert exc_info.value.status_code == 409


async def test_list_nonconformities_filter_by_workflow_type_reception(test_db: AsyncSession):
    """type_filter=RECEPTION must return only reception NCs, not temperature ones."""
    from datetime import date, datetime
    from unittest.mock import AsyncMock, MagicMock

    from app.modules.nonconformities.models import WorkflowType
    from app.modules.receptions.schemas import ReceptionItemCreate, ReceptionSessionCreate
    from app.modules.receptions.service import add_item, open_session
    from tests.integration.conftest import make_product, make_supplier

    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    # Create a temperature NC
    await _open_nc(test_db, seed, equip)

    # Create a reception NC
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    s3 = MagicMock()
    s3.upload_image = AsyncMock(return_value="bl/x.jpg")
    s3.object_url = MagicMock(return_value="http://s3.local/bl/x.jpg")
    session_payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    session = await open_session(session_payload, test_db, seed.ctx, seed.operator, None, s3)
    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-NC",
            dluo=date(2026, 12, 31),
            is_compliant=False,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    response = await list_nonconformities(test_db, seed.ctx, type_filter=WorkflowType.RECEPTION)
    assert all(item.workflow_type == WorkflowType.RECEPTION for item in response.items)
    assert len(response.items) == 1
    # Counts reflect all NCs regardless of filter
    assert response.total_open == 2


async def test_list_nonconformities_type_filter_temperature(test_db: AsyncSession):
    """type_filter=TEMPERATURE returns only temperature NCs."""
    from app.modules.nonconformities.models import WorkflowType

    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    await _open_nc(test_db, seed, equip)
    await _open_nc(test_db, seed, equip)

    response = await list_nonconformities(test_db, seed.ctx, type_filter=WorkflowType.TEMPERATURE)
    assert len(response.items) == 2
    assert all(item.workflow_type == WorkflowType.TEMPERATURE for item in response.items)


async def test_get_nonconformity_stats_counts_all_statuses(test_db: AsyncSession):
    """Stats counts must be correct across all four lifecycle states."""
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    # 2 OPEN
    await _open_nc(test_db, seed, equip)
    await _open_nc(test_db, seed, equip)

    # 1 IN_PROGRESS
    nc3 = await _open_nc(test_db, seed, equip)
    await acknowledge_nonconformity(nc3.id, test_db, seed.ctx, seed.operator)

    # 1 RESOLVED
    nc4 = await _open_nc(test_db, seed, equip)
    await acknowledge_nonconformity(nc4.id, test_db, seed.ctx, seed.operator)
    mock_s3 = MagicMock()
    mock_s3.upload_image = AsyncMock(return_value=None)
    mock_s3.object_url = MagicMock(return_value=None)
    await create_corrective_action(nc4.id, test_db, seed.ctx, seed.operator, mock_s3, "Résolu")

    stats = await get_nonconformity_stats(test_db, seed.ctx)
    assert stats.total == 4
    assert stats.total_open == 2
    assert stats.total_in_progress == 1
    assert stats.total_resolved == 1
    assert stats.total_closed == 0


async def test_acknowledge_nonconformity_not_found_raises_404(test_db: AsyncSession):
    from uuid import uuid4

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await acknowledge_nonconformity(uuid4(), test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 404


async def test_close_nonconformity_not_found_raises_404(test_db: AsyncSession):
    from uuid import uuid4

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await close_nonconformity(uuid4(), CloseNonConformityRequest(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404
