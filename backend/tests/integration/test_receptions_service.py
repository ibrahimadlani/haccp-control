"""Integration tests for app/modules/receptions/service.py."""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import SupplierStatus
from app.modules.nonconformities.models import NonConformity, NonConformityStatus, WorkflowType
from app.modules.receptions.schemas import ReceptionItemCreate, ReceptionSessionCreate
from app.modules.receptions.service import add_item, close_session, get_session, open_session
from tests.integration.conftest import (
    make_base_seed,
    make_product,
    make_supplier,
)


def _mock_s3():
    s3 = MagicMock()
    s3.upload_image = AsyncMock(return_value="bl-photos/test.jpg")
    s3.object_url = MagicMock(return_value="http://s3.local/test.jpg")
    return s3


# ── Open session ──────────────────────────────────────────────────────────────


async def test_open_session_creates_session(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)

    payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    result = await open_session(payload, test_db, seed.ctx, seed.operator, None, _mock_s3())

    assert result.id is not None
    assert result.supplier_id == supplier.id
    assert result.status.upper() == "OPEN"


# ── Add item ──────────────────────────────────────────────────────────────────


async def test_add_item_compliant_no_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, status=SupplierStatus.APPROVED)
    product = await make_product(test_db, seed.est, supplier)

    session_payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    session = await open_session(
        session_payload, test_db, seed.ctx, seed.operator, None, _mock_s3()
    )

    item_payload = ReceptionItemCreate(
        product_id=product.id,
        lot_number="LOT-001",
        dluo=date(2025, 12, 31),
        is_compliant=True,
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert item.is_compliant is True

    ncs = (
        (
            await test_db.execute(
                select(NonConformity).where(NonConformity.establishment_id == seed.est.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(ncs) == 0


async def test_add_item_non_compliant_creates_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, status=SupplierStatus.APPROVED)
    product = await make_product(test_db, seed.est, supplier)

    session_payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    session = await open_session(
        session_payload, test_db, seed.ctx, seed.operator, None, _mock_s3()
    )

    item_payload = ReceptionItemCreate(
        product_id=product.id,
        lot_number="LOT-002",
        dluo=date(2025, 12, 31),
        is_compliant=False,  # explicitly non-compliant
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert item.is_compliant is False

    ncs = (
        (
            await test_db.execute(
                select(NonConformity).where(
                    NonConformity.establishment_id == seed.est.id,
                    NonConformity.workflow_type == WorkflowType.RECEPTION,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(ncs) == 1
    assert ncs[0].status == NonConformityStatus.OPEN


async def test_add_item_to_closed_session_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)

    session_payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    session = await open_session(
        session_payload, test_db, seed.ctx, seed.operator, None, _mock_s3()
    )
    await close_session(session.id, test_db, seed.ctx)

    item_payload = ReceptionItemCreate(
        product_id=product.id,
        lot_number="LOT-003",
        dluo=date(2025, 12, 31),
        is_compliant=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert exc_info.value.status_code == 409


# ── Close session ─────────────────────────────────────────────────────────────


async def test_close_session(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)

    session_payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(UTC),
    )
    session = await open_session(
        session_payload, test_db, seed.ctx, seed.operator, None, _mock_s3()
    )
    result = await close_session(session.id, test_db, seed.ctx)
    assert result.status.upper() == "CLOSED"


# ── Get session ───────────────────────────────────────────────────────────────


async def test_get_session_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await get_session(uuid.uuid4(), test_db, seed.ctx, _mock_s3())
    assert exc_info.value.status_code == 404
