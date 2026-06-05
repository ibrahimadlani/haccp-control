"""Integration tests for app/modules/catalog/service.py."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import SupplierStatus
from app.modules.catalog.schemas import (
    ProductCreate,
    ProductUpdate,
    ReceptionProductCreate,
    SupplierCreate,
    SupplierUpdate,
)
from app.modules.catalog.service import (
    create_product,
    create_product_for_reception,
    create_supplier,
    get_product_by_id,
    get_products,
    get_supplier_by_id,
    get_suppliers,
    list_products_for_reception,
    soft_delete_product,
    soft_delete_supplier,
    update_product,
    update_supplier,
)
from tests.integration.conftest import (
    make_base_seed,
    make_establishment,
    make_establishment_ctx,
    make_organisation,
    make_product,
    make_supplier,
)

# ── Supplier CRUD ─────────────────────────────────────────────────────────────


async def test_create_supplier(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = SupplierCreate(name="Boucherie Martin", status=SupplierStatus.APPROVED)
    result = await create_supplier(payload, test_db, seed.ctx)
    assert result.name == "Boucherie Martin"
    assert result.id is not None


async def test_get_suppliers_returns_created(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await make_supplier(test_db, seed.est, name="Fournisseur A")
    await make_supplier(test_db, seed.est, name="Fournisseur B")

    response = await get_suppliers(test_db, seed.ctx)
    names = {s.name for s in response.items}
    assert "Fournisseur A" in names
    assert "Fournisseur B" in names


async def test_get_suppliers_status_filter(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await make_supplier(test_db, seed.est, status=SupplierStatus.APPROVED)
    await make_supplier(test_db, seed.est, status=SupplierStatus.PENDING)

    approved = await get_suppliers(test_db, seed.ctx, status_filter=SupplierStatus.APPROVED)
    assert all(s.status == SupplierStatus.APPROVED for s in approved.items)
    assert len(approved.items) == 1


async def test_get_supplier_by_id_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    import uuid

    with pytest.raises(HTTPException) as exc_info:
        await get_supplier_by_id(uuid.uuid4(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_update_supplier(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, name="Old Name")

    payload = SupplierUpdate(name="New Name")
    result = await update_supplier(supplier.id, payload, test_db, seed.ctx)
    assert result.name == "New Name"


async def test_soft_delete_supplier_deactivates(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)

    await soft_delete_supplier(supplier.id, test_db, seed.ctx)
    from sqlalchemy import select

    from app.modules.catalog.models import Supplier

    updated = (
        await test_db.execute(select(Supplier).where(Supplier.id == supplier.id))
    ).scalar_one()
    assert updated.is_active is False


async def test_supplier_scoped_to_establishment(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    other_org = await make_organisation(test_db)
    other_est = await make_establishment(test_db, other_org)
    other_supplier = await make_supplier(test_db, other_est)

    with pytest.raises(HTTPException) as exc_info:
        await get_supplier_by_id(other_supplier.id, test_db, seed.ctx)
    assert exc_info.value.status_code == 404


# ── Product CRUD ──────────────────────────────────────────────────────────────


async def test_create_product_approved_supplier(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, status=SupplierStatus.APPROVED)

    payload = ProductCreate(
        name="Bœuf haché",
        supplier_id=supplier.id,
        has_temperature_control=False,
    )
    result = await create_product(payload, test_db, seed.ctx)
    assert result.name == "Bœuf haché"
    assert result.supplier_id == supplier.id


async def test_create_product_inactive_supplier_raises_422(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, status=SupplierStatus.PENDING)
    supplier.is_active = False
    await test_db.flush()

    payload = ProductCreate(
        name="Produit test",
        supplier_id=supplier.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_product(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 422


async def test_create_product_supplier_from_other_establishment_raises_422(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    other_org = await make_organisation(test_db)
    other_est = await make_establishment(test_db, other_org)
    foreign_supplier = await make_supplier(test_db, other_est, status=SupplierStatus.APPROVED)

    payload = ProductCreate(name="Produit étranger", supplier_id=foreign_supplier.id)
    with pytest.raises(HTTPException) as exc_info:
        await create_product(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 422


async def test_soft_delete_product(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)

    await soft_delete_product(product.id, test_db, seed.ctx)
    from sqlalchemy import select

    from app.modules.catalog.models import Product

    updated = (await test_db.execute(select(Product).where(Product.id == product.id))).scalar_one()
    assert updated.is_active is False


async def test_list_products_for_reception_no_manager_required(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    await make_product(test_db, seed.est, supplier, name="Produit réception")

    # Use non-manager context — should NOT raise 403
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
    response = await list_products_for_reception(test_db, non_manager_ctx)
    assert any(p.name == "Produit réception" for p in response.items)


# ── Supplier filters ──────────────────────────────────────────────────────────


async def test_get_suppliers_include_inactive_returns_soft_deleted(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est, name="Fournisseur désactivé")
    await soft_delete_supplier(supplier.id, test_db, seed.ctx)

    response = await get_suppliers(test_db, seed.ctx, include_inactive=True)
    names = {s.name for s in response.items}
    assert "Fournisseur désactivé" in names


async def test_update_supplier_not_found_raises_404(test_db: AsyncSession):
    import uuid

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await update_supplier(uuid.uuid4(), SupplierUpdate(name="X"), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_soft_delete_supplier_already_inactive_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    await soft_delete_supplier(supplier.id, test_db, seed.ctx)

    with pytest.raises(HTTPException) as exc_info:
        await soft_delete_supplier(supplier.id, test_db, seed.ctx)
    assert exc_info.value.status_code == 404


# ── Product filters and update ────────────────────────────────────────────────


async def test_get_products_supplier_filter(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier_a = await make_supplier(test_db, seed.est, name="Fournisseur A")
    supplier_b = await make_supplier(test_db, seed.est, name="Fournisseur B")
    await make_product(test_db, seed.est, supplier_a, name="Produit A")
    await make_product(test_db, seed.est, supplier_b, name="Produit B")

    response = await get_products(test_db, seed.ctx, supplier_id=supplier_a.id)
    names = {p.name for p in response.items}
    assert "Produit A" in names
    assert "Produit B" not in names


async def test_get_products_include_inactive(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier, name="Produit archivé")
    await soft_delete_product(product.id, test_db, seed.ctx)

    response = await get_products(test_db, seed.ctx, include_inactive=True)
    names = {p.name for p in response.items}
    assert "Produit archivé" in names


async def test_get_product_by_id_not_found_raises_404(test_db: AsyncSession):
    import uuid

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await get_product_by_id(uuid.uuid4(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_update_product_name(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier, name="Ancien nom")

    result = await update_product(product.id, ProductUpdate(name="Nouveau nom"), test_db, seed.ctx)
    assert result.name == "Nouveau nom"


async def test_update_product_not_found_raises_404(test_db: AsyncSession):
    import uuid

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await update_product(uuid.uuid4(), ProductUpdate(name="X"), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


# ── Reception-context product CRUD ────────────────────────────────────────────


async def test_create_product_for_reception(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)

    payload = ReceptionProductCreate(
        name="Produit rapide",
        supplier_id=supplier.id,
        has_temperature_control=False,
    )
    result = await create_product_for_reception(payload, test_db, seed.ctx)
    assert result.name == "Produit rapide"
    assert result.id is not None
