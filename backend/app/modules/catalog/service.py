"""
Business logic for the Catalog domain (Suppliers and Products).

Provides two service layers:

1. **Supplier CRUD** — all operations require manager rights via
   ``ensure_admin_org_access``.  Soft deletion sets ``is_active = False``
   without removing the row, preserving historical reception records that
   reference the supplier.

2. **Product CRUD** — standard manager-facing CRUD plus a separate
   reception-context CRUD subset (``*_for_reception`` functions) that is
   called by the receptions module without requiring manager rights.
   Both use the ``_get_active_product`` / ``_assert_supplier_in_scope``
   private helpers for consistent multi-tenant scoping.

All queries include an ``establishment_id`` filter to enforce strict
tenant isolation — a manager of establishment A cannot read or modify
catalog data belonging to establishment B.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.modules.catalog.models import Product, Supplier, SupplierStatus
from app.modules.catalog.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    ReceptionProductCreate,
    ReceptionProductListResponse,
    ReceptionProductResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.modules.personnel.service import ensure_admin_org_access

# ── Suppliers ─────────────────────────────────────────────────────────────────


async def get_suppliers(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    include_inactive: bool = False,
    status_filter: SupplierStatus | None = None,
) -> SupplierListResponse:
    """Return suppliers for the current establishment with optional filters.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        include_inactive (bool): When ``True``, include soft-deleted suppliers.
            Defaults to ``False``.
        status_filter (SupplierStatus | None): When set, only suppliers with
            this approval status are returned.

    Returns:
        SupplierListResponse: Suppliers sorted alphabetically by name.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)

    where = [Supplier.establishment_id == establishment.etablissement_id]
    if not include_inactive:
        where.append(Supplier.is_active.is_(True))
    if status_filter is not None:
        where.append(Supplier.status == status_filter)

    result = await db.execute(select(Supplier).where(*where).order_by(Supplier.name.asc()))
    suppliers = result.scalars().all()
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in suppliers],
        total=len(suppliers),
    )


async def get_supplier_by_id(
    supplier_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SupplierResponse:
    """Return a single supplier by primary key, scoped to the current establishment.

    Args:
        supplier_id (UUID): The supplier's primary key.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        SupplierResponse: The supplier record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the supplier does not exist or belongs
            to a different establishment.
    """
    await ensure_admin_org_access(db, establishment)
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.establishment_id == establishment.etablissement_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fournisseur introuvable pour cet établissement.",
        )
    return SupplierResponse.model_validate(supplier)


async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SupplierResponse:
    """Create a new supplier for the current establishment.

    Args:
        payload (SupplierCreate): Validated supplier data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        SupplierResponse: The created supplier record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)
    supplier = Supplier(establishment_id=establishment.etablissement_id, **payload.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


async def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SupplierResponse:
    """Partially update a supplier's fields (PATCH semantics).

    Args:
        supplier_id (UUID): The supplier to update.
        payload (SupplierUpdate): Fields to update. Only supplied fields are applied.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        SupplierResponse: The updated supplier record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the supplier is not in scope.
    """
    await ensure_admin_org_access(db, establishment)
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.establishment_id == establishment.etablissement_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fournisseur introuvable pour cet établissement.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await db.commit()
    await db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


async def soft_delete_supplier(
    supplier_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Deactivate a supplier by setting ``is_active = False``.

    Physical deletion is not used because historical reception records
    reference the supplier and must remain traceable.

    Args:
        supplier_id (UUID): The supplier to deactivate.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the supplier is not found or already inactive.
    """
    await ensure_admin_org_access(db, establishment)
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.establishment_id == establishment.etablissement_id,
            Supplier.is_active.is_(True),
        )
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fournisseur introuvable ou déjà désactivé.",
        )
    supplier.is_active = False
    await db.commit()


# ── Products ──────────────────────────────────────────────────────────────────


async def get_products(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    supplier_id: UUID | None = None,
    include_inactive: bool = False,
) -> ProductListResponse:
    """Return catalog products for the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        supplier_id (UUID | None): When set, filters to products from this supplier.
        include_inactive (bool): When ``True``, includes soft-deleted products.

    Returns:
        ProductListResponse: Products sorted alphabetically by name.
    """
    where = [Product.establishment_id == establishment.etablissement_id]
    if not include_inactive:
        where.append(Product.is_active.is_(True))
    if supplier_id is not None:
        where.append(Product.supplier_id == supplier_id)

    result = await db.execute(select(Product).where(*where).order_by(Product.name.asc()))
    products = result.scalars().all()
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=len(products),
    )


async def get_product_by_id(
    product_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductResponse:
    """Return a single active product by primary key.

    Args:
        product_id (UUID): The product's primary key.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ProductResponse: The product record.

    Raises:
        HTTPException: 404 Not Found if the product does not exist, is inactive,
            or belongs to a different establishment.
    """
    product = await _get_active_product(db, establishment, product_id)
    return ProductResponse.model_validate(product)


async def create_product(
    payload: ProductCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductResponse:
    """Create a new catalog product and validate that its supplier is in scope.

    Args:
        payload (ProductCreate): Validated product data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ProductResponse: The created product record.

    Raises:
        HTTPException: 422 Unprocessable Entity if the supplier is not active
            or belongs to a different establishment.
    """
    await _assert_supplier_in_scope(db, establishment, payload.supplier_id)
    product = Product(establishment_id=establishment.etablissement_id, **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductResponse:
    """Partially update a catalog product (PATCH semantics).

    When ``supplier_id`` is included in the payload, the new supplier is
    validated to be active and in the same establishment scope.

    Args:
        product_id (UUID): The product to update.
        payload (ProductUpdate): Fields to update.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ProductResponse: The updated product record.

    Raises:
        HTTPException: 404 Not Found if the product is not in scope.
        HTTPException: 422 Unprocessable Entity if the new supplier is invalid.
    """
    product = await _get_active_product(db, establishment, product_id)
    updates = payload.model_dump(exclude_unset=True)
    if "supplier_id" in updates and updates["supplier_id"] is not None:
        await _assert_supplier_in_scope(db, establishment, updates["supplier_id"])
    for field, value in updates.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


async def soft_delete_product(
    product_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Deactivate a catalog product by setting ``is_active = False``.

    Args:
        product_id (UUID): The product to deactivate.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the product is not in scope.
    """
    product = await _get_active_product(db, establishment, product_id)
    product.is_active = False
    await db.commit()


# ── Reception-context product CRUD (called by receptions module) ──────────────


async def list_products_for_reception(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    supplier_id: UUID | None = None,
) -> ReceptionProductListResponse:
    """Return active products for the tablet reception workflow.

    Unlike the manager-facing ``get_products``, this function does not
    require manager rights so tablet operators can access the product list.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        supplier_id (UUID | None): Optional supplier filter.

    Returns:
        ReceptionProductListResponse: Active products sorted by name.
    """
    where = [
        Product.establishment_id == establishment.etablissement_id,
        Product.is_active.is_(True),
    ]
    if supplier_id is not None:
        where.append(Product.supplier_id == supplier_id)
    result = await db.execute(select(Product).where(*where).order_by(Product.name))
    products = result.scalars().all()
    return ReceptionProductListResponse(
        items=[ReceptionProductResponse.model_validate(p) for p in products],
        total=len(products),
    )


async def create_product_for_reception(
    payload: ReceptionProductCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ReceptionProductResponse:
    """Quickly create a product during an active reception session.

    Used when an operator scans a product that is not yet in the catalog.
    The product is created with minimal data and can be enriched later via
    the manager-facing catalog endpoints.

    Args:
        payload (ReceptionProductCreate): Minimal product data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ReceptionProductResponse: The created product in reception-context format.
    """
    product = Product(
        establishment_id=establishment.etablissement_id,
        supplier_id=payload.supplier_id,
        name=payload.name,
        internal_reference=payload.internal_reference,
        has_temperature_control=payload.has_temperature_control,
        min_temperature=payload.min_temperature,
        max_temperature=payload.max_temperature,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return ReceptionProductResponse.model_validate(product)


async def update_product_for_reception(
    product_id: UUID,
    payload: ReceptionProductCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ReceptionProductResponse:
    """Update a product's reception-relevant fields during an active session.

    Args:
        product_id (UUID): The product to update.
        payload (ReceptionProductCreate): Updated product data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ReceptionProductResponse: The updated product.

    Raises:
        HTTPException: 404 Not Found if the product is not in scope.
    """
    product = await _get_active_product(db, establishment, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return ReceptionProductResponse.model_validate(product)


async def soft_delete_product_for_reception(
    product_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Deactivate a product from within the reception workflow.

    Args:
        product_id (UUID): The product to deactivate.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the product is not in scope.
    """
    product = await _get_active_product(db, establishment, product_id)
    product.is_active = False
    await db.commit()


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_active_product(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    product_id: UUID,
) -> Product:
    """Load an active product scoped to the current establishment.

    Combines the PK lookup, the ``establishment_id`` tenant filter, and the
    ``is_active`` soft-delete filter in a single query.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        product_id (UUID): The product's primary key.

    Returns:
        Product: The matching active product ORM instance.

    Raises:
        HTTPException: 404 Not Found if no active product with that ID exists
            in the current establishment.
    """
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.establishment_id == establishment.etablissement_id,
            Product.is_active.is_(True),
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable ou inactif."
        )
    return product


async def _assert_supplier_in_scope(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    supplier_id: UUID,
) -> None:
    """Assert that a supplier exists, is active, and belongs to the current establishment.

    Called before creating or reassigning a product to prevent cross-tenant
    supplier references.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        supplier_id (UUID): The supplier primary key to validate.

    Raises:
        HTTPException: 422 Unprocessable Entity if the supplier is not found,
            inactive, or belongs to a different establishment.
    """
    result = await db.execute(
        select(Supplier.id).where(
            Supplier.id == supplier_id,
            Supplier.establishment_id == establishment.etablissement_id,
            Supplier.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fournisseur introuvable ou inactif pour cet établissement.",
        )
