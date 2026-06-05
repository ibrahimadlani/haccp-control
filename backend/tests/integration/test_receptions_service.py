"""Integration tests for app/modules/receptions/service.py."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product, SupplierStatus
from app.modules.nonconformities.models import NonConformity, NonConformityStatus, WorkflowType
from app.modules.receptions.schemas import ReceptionItemCreate, ReceptionSessionCreate
from app.modules.receptions.service import (
    add_item,
    close_session,
    get_session,
    open_session,
    search_reception_items_by_lot,
)
from tests.integration.conftest import (
    make_base_seed,
    make_product,
    make_supplier,
)


def _mock_s3(upload_key: str = "bl-photos/test.jpg", base_url: str = "http://s3.local"):
    s3 = MagicMock()
    s3.upload_image = AsyncMock(return_value=upload_key)
    s3.object_url = MagicMock(side_effect=lambda key: f"{base_url}/{key}" if key else None)
    return s3


async def _open_session(test_db, seed, supplier=None, s3=None, **session_kwargs):
    """Helper: open a reception session with sensible defaults."""
    if supplier is None:
        supplier = await make_supplier(test_db, seed.est)
    payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(timezone.utc),
        **session_kwargs,
    )
    return await open_session(payload, test_db, seed.ctx, seed.operator, None, s3 or _mock_s3())


async def _make_temp_controlled_product(test_db, est, supplier, min_temp=0.0, max_temp=4.0):
    """Helper: create a product with cold-chain temperature control."""
    product = Product(
        establishment_id=est.id,
        supplier_id=supplier.id,
        name=f"Produit froid {uuid.uuid4().hex[:4]}",
        has_temperature_control=True,
        min_temperature=min_temp,
        max_temperature=max_temp,
    )
    test_db.add(product)
    await test_db.flush()
    return product


# ── Open session ──────────────────────────────────────────────────────────────


async def test_open_session_creates_session(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)

    payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(timezone.utc),
    )
    result = await open_session(payload, test_db, seed.ctx, seed.operator, None, _mock_s3())

    assert result.id is not None
    assert result.supplier_id == supplier.id
    assert result.status.upper() == "OPEN"
    assert result.truck_condition_ok is True  # default


async def test_open_session_truck_condition_ok_false_stored(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed, truck_condition_ok=False)
    assert session.truck_condition_ok is False


async def test_open_session_truck_condition_ok_true_stored(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed, truck_condition_ok=True)
    assert session.truck_condition_ok is True


async def test_open_session_with_bl_photo_uploads_to_s3(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    s3 = _mock_s3(upload_key="bl-photos/receipt-xyz.jpg")

    mock_file = MagicMock()
    payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(timezone.utc),
    )
    result = await open_session(payload, test_db, seed.ctx, seed.operator, mock_file, s3)

    s3.upload_image.assert_awaited_once_with(mock_file, prefix="bl-photos")
    assert result.bl_photo_url is not None
    assert "bl-photos/receipt-xyz.jpg" in result.bl_photo_url


async def test_open_session_no_bl_photo_no_url(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed)
    assert session.bl_photo_url is None


async def test_open_session_timezone_naive_datetime_normalised(test_db: AsyncSession):
    """A tz-naive received_at is interpreted as site local time, not UTC."""
    seed = await make_base_seed(test_db)
    naive_dt = datetime(2025, 6, 1, 10, 0, 0)  # no tzinfo
    supplier = await make_supplier(test_db, seed.est)
    payload = ReceptionSessionCreate(supplier_id=supplier.id, received_at=naive_dt)
    result = await open_session(payload, test_db, seed.ctx, seed.operator, None, _mock_s3())
    assert result.received_at.tzinfo is not None  # normalised to tz-aware


# ── Add item ──────────────────────────────────────────────────────────────────


async def test_add_item_compliant_no_nc(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, status=SupplierStatus.APPROVED)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    item = await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-001",
            dluo=date(2026, 12, 31),
            is_compliant=True,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    assert item.is_compliant is True
    assert item.packaging_ok is True
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
    session = await _open_session(test_db, seed, supplier=supplier)

    item = await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-002",
            dluo=date(2026, 12, 31),
            is_compliant=False,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

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


async def test_add_item_packaging_ok_false_forces_non_compliant_and_creates_nc(
    test_db: AsyncSession,
):
    """packaging_ok=False must override is_compliant=True server-side."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    item = await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-PKG",
            dluo=date(2026, 12, 31),
            packaging_ok=False,
            is_compliant=False,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    assert item.packaging_ok is False
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


async def test_add_item_packaging_ok_false_overrides_client_compliant_true(
    test_db: AsyncSession,
):
    """Server must enforce: packaging_ok=False → is_compliant=False regardless of client."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    # Bypass schema validation to test service-layer enforcement independently.
    item_payload = ReceptionItemCreate.model_construct(
        product_id=product.id,
        lot_number="LOT-BYPASS",
        dluo=date(2026, 12, 31),
        packaging_ok=False,
        is_compliant=True,  # client tries to say compliant despite bad packaging
        measured_temperature=None,
        product_min_temp=None,
        product_max_temp=None,
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)

    assert item.is_compliant is False  # service must have forced False


async def test_add_item_temperature_out_of_range_forced_non_compliant(test_db: AsyncSession):
    """Server re-validates temperature even if client sends is_compliant=True."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await _make_temp_controlled_product(
        test_db, seed.est, supplier, min_temp=0.0, max_temp=4.0
    )
    session = await _open_session(test_db, seed, supplier=supplier)

    # Temperature 8°C is above max 4°C; client lies and says compliant.
    item_payload = ReceptionItemCreate.model_construct(
        product_id=product.id,
        lot_number="LOT-TEMP",
        dluo=date(2026, 12, 31),
        packaging_ok=True,
        is_compliant=True,
        measured_temperature=8.0,
        product_min_temp=None,
        product_max_temp=None,
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert item.is_compliant is False


async def test_add_item_temperature_at_min_boundary_is_compliant(test_db: AsyncSession):
    """Temperature exactly at min threshold must be compliant (inclusive boundary)."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await _make_temp_controlled_product(
        test_db, seed.est, supplier, min_temp=0.0, max_temp=4.0
    )
    session = await _open_session(test_db, seed, supplier=supplier)

    item_payload = ReceptionItemCreate.model_construct(
        product_id=product.id,
        lot_number="LOT-MIN",
        dluo=date(2026, 12, 31),
        packaging_ok=True,
        is_compliant=True,
        measured_temperature=0.0,
        product_min_temp=None,
        product_max_temp=None,
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert item.is_compliant is True


async def test_add_item_temperature_at_max_boundary_is_compliant(test_db: AsyncSession):
    """Temperature exactly at max threshold must be compliant (inclusive boundary)."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await _make_temp_controlled_product(
        test_db, seed.est, supplier, min_temp=0.0, max_temp=4.0
    )
    session = await _open_session(test_db, seed, supplier=supplier)

    item_payload = ReceptionItemCreate.model_construct(
        product_id=product.id,
        lot_number="LOT-MAX",
        dluo=date(2026, 12, 31),
        packaging_ok=True,
        is_compliant=True,
        measured_temperature=4.0,
        product_min_temp=None,
        product_max_temp=None,
    )
    item = await add_item(session.id, item_payload, test_db, seed.ctx, seed.operator)
    assert item.is_compliant is True


async def test_add_item_product_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed)

    with pytest.raises(HTTPException) as exc_info:
        await add_item(
            session.id,
            ReceptionItemCreate(
                product_id=uuid.uuid4(),
                lot_number="LOT-X",
                dluo=date(2026, 12, 31),
                is_compliant=True,
            ),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 404


async def test_add_item_inactive_product_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    product.is_active = False
    await test_db.flush()
    session = await _open_session(test_db, seed, supplier=supplier)

    with pytest.raises(HTTPException) as exc_info:
        await add_item(
            session.id,
            ReceptionItemCreate(
                product_id=product.id,
                lot_number="LOT-DEAD",
                dluo=date(2026, 12, 31),
                is_compliant=True,
            ),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 404


async def test_add_item_to_closed_session_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)
    await close_session(session.id, test_db, seed.ctx)

    with pytest.raises(HTTPException) as exc_info:
        await add_item(
            session.id,
            ReceptionItemCreate(
                product_id=product.id,
                lot_number="LOT-003",
                dluo=date(2026, 12, 31),
                is_compliant=True,
            ),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 409


async def test_add_item_wrong_establishment_product_raises_404(test_db: AsyncSession):
    """A product belonging to a different establishment must not be scannable."""
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
    other_supplier = await make_supplier(test_db, other_est)
    other_product = await make_product(test_db, other_est, other_supplier)

    session = await _open_session(test_db, seed)

    with pytest.raises(HTTPException) as exc_info:
        await add_item(
            session.id,
            ReceptionItemCreate(
                product_id=other_product.id,
                lot_number="LOT-OTHER",
                dluo=date(2026, 12, 31),
                is_compliant=True,
            ),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 404


# ── Close session ─────────────────────────────────────────────────────────────


async def test_close_session_transitions_to_closed(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed)
    result = await close_session(session.id, test_db, seed.ctx)
    assert result.status.upper() == "CLOSED"
    assert result.closed_at is not None


async def test_close_session_already_closed_raises_409(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    session = await _open_session(test_db, seed)
    await close_session(session.id, test_db, seed.ctx)

    with pytest.raises(HTTPException) as exc_info:
        await close_session(session.id, test_db, seed.ctx)
    assert exc_info.value.status_code == 409


async def test_close_session_wrong_establishment_raises_404(test_db: AsyncSession):
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

    session = await _open_session(test_db, seed)

    with pytest.raises(HTTPException) as exc_info:
        await close_session(session.id, test_db, other_ctx)
    assert exc_info.value.status_code == 404


# ── Get session ───────────────────────────────────────────────────────────────


async def test_get_session_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await get_session(uuid.uuid4(), test_db, seed.ctx, _mock_s3())
    assert exc_info.value.status_code == 404


async def test_get_session_includes_scanned_items(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-A",
            dluo=date(2026, 12, 31),
            is_compliant=True,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="LOT-B",
            dluo=date(2026, 6, 30),
            is_compliant=True,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    detail = await get_session(session.id, test_db, seed.ctx, _mock_s3())
    assert len(detail.items) == 2
    lot_numbers = {i.lot_number for i in detail.items}
    assert lot_numbers == {"LOT-A", "LOT-B"}


async def test_get_session_bl_photo_url_built_from_key(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    s3 = _mock_s3(upload_key="bl-photos/abc.jpg", base_url="https://cdn.example.com")
    mock_file = MagicMock()
    payload = ReceptionSessionCreate(
        supplier_id=supplier.id,
        received_at=datetime.now(timezone.utc),
    )
    session = await open_session(payload, test_db, seed.ctx, seed.operator, mock_file, s3)

    detail = await get_session(session.id, test_db, seed.ctx, s3)
    assert detail.bl_photo_url == "https://cdn.example.com/bl-photos/abc.jpg"


# ── Lot search ────────────────────────────────────────────────────────────────


async def test_search_reception_items_by_lot_empty_query_returns_empty(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await search_reception_items_by_lot("", test_db, seed.ctx)
    assert result == []


async def test_search_reception_items_by_lot_whitespace_only_returns_empty(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    result = await search_reception_items_by_lot("   ", test_db, seed.ctx)
    assert result == []


async def test_search_reception_items_by_lot_no_match_returns_empty(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await search_reception_items_by_lot("NONEXISTENT-9999", test_db, seed.ctx)
    assert result == []


async def test_search_reception_items_by_lot_exact_match(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="FRAISE-2025-01",
            dluo=date(2026, 1, 31),
            is_compliant=True,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    results = await search_reception_items_by_lot("FRAISE-2025-01", test_db, seed.ctx)
    assert len(results) == 1
    assert results[0].lot_number == "FRAISE-2025-01"
    assert results[0].product_name is not None


async def test_search_reception_items_by_lot_partial_match(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    for lot in ("LOT-ABC-001", "LOT-ABC-002", "UNRELATED-XYZ"):
        await add_item(
            session.id,
            ReceptionItemCreate(
                product_id=product.id,
                lot_number=lot,
                dluo=date(2026, 1, 31),
                is_compliant=True,
            ),
            test_db,
            seed.ctx,
            seed.operator,
        )

    results = await search_reception_items_by_lot("LOT-ABC", test_db, seed.ctx)
    assert len(results) == 2
    assert "UNRELATED-XYZ" not in {r.lot_number for r in results}


async def test_search_reception_items_by_lot_case_insensitive(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="UPPER-LOT-999",
            dluo=date(2026, 1, 31),
            is_compliant=True,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    results = await search_reception_items_by_lot("upper-lot", test_db, seed.ctx)
    assert len(results) == 1


async def test_search_reception_items_by_lot_scoped_to_establishment(test_db: AsyncSession):
    """Items from another establishment must not appear in search results."""
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
    other_supplier = await make_supplier(test_db, other_est)
    other_product = await make_product(test_db, other_est, other_supplier)

    other_session = await open_session(
        ReceptionSessionCreate(
            supplier_id=other_supplier.id,
            received_at=datetime.now(timezone.utc),
        ),
        test_db,
        other_ctx,
        other_user,
        None,
        _mock_s3(),
    )
    await add_item(
        other_session.id,
        ReceptionItemCreate(
            product_id=other_product.id,
            lot_number="SHARED-LOT-001",
            dluo=date(2026, 1, 31),
            is_compliant=True,
        ),
        test_db,
        other_ctx,
        other_user,
    )

    results = await search_reception_items_by_lot("SHARED-LOT", test_db, seed.ctx)
    assert len(results) == 0


async def test_search_reception_items_includes_packaging_flag(test_db: AsyncSession):
    """Search results carry packaging_ok and is_compliant for recall triage."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await _open_session(test_db, seed, supplier=supplier)

    await add_item(
        session.id,
        ReceptionItemCreate(
            product_id=product.id,
            lot_number="DAMAGED-PKG-001",
            dluo=date(2026, 1, 31),
            packaging_ok=False,
            is_compliant=False,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )

    results = await search_reception_items_by_lot("DAMAGED-PKG", test_db, seed.ctx)
    assert len(results) == 1
    assert results[0].packaging_ok is False
    assert results[0].is_compliant is False
