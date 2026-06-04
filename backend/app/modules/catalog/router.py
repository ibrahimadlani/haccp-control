"""
FastAPI router for the Catalog domain (Suppliers and Products).

Exposes CRUD endpoints for the manager-facing catalog:

- ``GET/POST /suppliers`` — list and create suppliers.
- ``GET/PATCH/DELETE /suppliers/{supplier_id}`` — read, update, and
  soft-delete a supplier.
- ``GET/POST /products`` — list and create catalog products.
- ``GET/PATCH/DELETE /products/{product_id}`` — read, update, and
  soft-delete a product.

All endpoints require a valid establishment JWT (``CurrentSite``).
Write operations additionally require manager rights, enforced in the
service layer via ``ensure_admin_org_access``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.modules.catalog import service
from app.modules.catalog.models import SupplierStatus
from app.modules.catalog.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(tags=["Catalogue"], dependencies=[Depends(require_feature(Feature.SUPPLIERS))])


# ── Suppliers ─────────────────────────────────────────────────────────────────


@router.get("/suppliers", response_model=SupplierListResponse)
async def list_suppliers(
    db: DatabaseSession,
    establishment: CurrentSite,
    include_inactive: Annotated[bool, Query()] = False,
    status_filter: Annotated[SupplierStatus | None, Query(alias="status")] = None,
) -> SupplierListResponse:
    """List suppliers for the current establishment with optional filters.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        include_inactive (bool): Include soft-deleted suppliers. Defaults to ``False``.
        status_filter (SupplierStatus | None): Filter by approval status.

    Returns:
        SupplierListResponse: Suppliers sorted alphabetically.
    """
    return await service.get_suppliers(db, establishment, include_inactive, status_filter)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> SupplierResponse:
    """Return a single supplier by primary key.

    Args:
        supplier_id (UUID): The supplier's primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SupplierResponse: The supplier record.

    Raises:
        HTTPException: 404 Not Found if the supplier is not in scope.
    """
    return await service.get_supplier_by_id(supplier_id, db, establishment)


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreate, db: DatabaseSession, establishment: CurrentSite
) -> SupplierResponse:
    """Create a new supplier for the current establishment.

    Args:
        payload (SupplierCreate): Validated supplier data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SupplierResponse: The created supplier.
    """
    return await service.create_supplier(payload, db, establishment)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID, payload: SupplierUpdate, db: DatabaseSession, establishment: CurrentSite
) -> SupplierResponse:
    """Partially update a supplier's fields.

    Args:
        supplier_id (UUID): The supplier to update.
        payload (SupplierUpdate): Fields to update (PATCH semantics).
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SupplierResponse: The updated supplier.
    """
    return await service.update_supplier(supplier_id, payload, db, establishment)


@router.delete("/suppliers/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> None:
    """Soft-delete a supplier by setting ``is_active = False``.

    Args:
        supplier_id (UUID): The supplier to deactivate.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Raises:
        HTTPException: 404 Not Found if the supplier is not in scope.
    """
    await service.soft_delete_supplier(supplier_id, db, establishment)


# ── Products ──────────────────────────────────────────────────────────────────


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    db: DatabaseSession,
    establishment: CurrentSite,
    supplier_id: Annotated[UUID | None, Query()] = None,
    include_inactive: Annotated[bool, Query()] = False,
) -> ProductListResponse:
    """List catalog products for the current establishment.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        supplier_id (UUID | None): Optional supplier filter.
        include_inactive (bool): Include soft-deleted products. Defaults to ``False``.

    Returns:
        ProductListResponse: Products sorted alphabetically.
    """
    return await service.get_products(db, establishment, supplier_id, include_inactive)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> ProductResponse:
    """Return a single active product by primary key.

    Args:
        product_id (UUID): The product's primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ProductResponse: The product record.

    Raises:
        HTTPException: 404 Not Found if the product is not in scope.
    """
    return await service.get_product_by_id(product_id, db, establishment)


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate, db: DatabaseSession, establishment: CurrentSite
) -> ProductResponse:
    """Create a new catalog product.

    Args:
        payload (ProductCreate): Validated product data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ProductResponse: The created product.

    Raises:
        HTTPException: 422 Unprocessable Entity if the supplier is not in scope.
    """
    return await service.create_product(payload, db, establishment)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID, payload: ProductUpdate, db: DatabaseSession, establishment: CurrentSite
) -> ProductResponse:
    """Partially update a catalog product.

    Args:
        product_id (UUID): The product to update.
        payload (ProductUpdate): Fields to update (PATCH semantics).
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ProductResponse: The updated product.
    """
    return await service.update_product(product_id, payload, db, establishment)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: UUID, db: DatabaseSession, establishment: CurrentSite) -> None:
    """Soft-delete a catalog product.

    Args:
        product_id (UUID): The product to deactivate.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.soft_delete_product(product_id, db, establishment)
