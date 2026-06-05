"""
FastAPI router for the Receptions domain.

Exposes two groups of endpoints:

**Products (reception manager CRUD):**
- ``GET/POST /products`` — list and create products for the tablet reception workflow.
- ``PATCH/DELETE /products/{product_id}``

**Reception Sessions:**
- ``POST  /reception-sessions`` — open a new session (multipart: supplier,
  delivery time, optional BL photo).
- ``GET   /reception-sessions/{session_id}`` — load session detail with items.
- ``POST  /reception-sessions/{session_id}/items`` — scan a product line.
- ``PATCH /reception-sessions/{session_id}/close`` — confirm and close session.

All endpoints require an establishment JWT (``CurrentSite``).  Write
operations on sessions and items additionally require ``CurrentOperator``
(PIN authentication on the shared tablet).  S3 is injected via the
``S3Dep`` alias for session open and read endpoints.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.core.s3 import S3Service, get_s3_service
from app.modules.catalog.schemas import (
    ReceptionProductCreate,
    ReceptionProductListResponse,
    ReceptionProductResponse,
)
from app.modules.receptions import service
from app.modules.receptions.schemas import (
    ReceptionItemCreate,
    ReceptionItemResponse,
    ReceptionSessionCreate,
    ReceptionSessionDetailResponse,
    ReceptionSessionResponse,
)

router = APIRouter(tags=["Réception"], dependencies=[Depends(require_feature(Feature.RECEPTIONS))])

# Typed alias for the injected S3 service to keep endpoint signatures concise.
S3Dep = Annotated[S3Service, Depends(get_s3_service)]


# ── Products (reception manager CRUD) ─────────────────────────────────────────


@router.get("/products", response_model=ReceptionProductListResponse)
async def list_products(
    db: DatabaseSession,
    establishment: CurrentSite,
    supplier_id: Annotated[UUID | None, None] = None,
) -> ReceptionProductListResponse:
    """List active products for the tablet reception picker.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        supplier_id (UUID | None): Optional supplier filter.

    Returns:
        ReceptionProductListResponse: Active products sorted by name.
    """
    return await service.list_products(db, establishment, supplier_id)


@router.post("/products", response_model=ReceptionProductResponse, status_code=201)
async def create_product(
    payload: ReceptionProductCreate, db: DatabaseSession, establishment: CurrentSite
) -> ReceptionProductResponse:
    """Create a product during an active reception session.

    Args:
        payload (ReceptionProductCreate): Minimal product data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ReceptionProductResponse: The created product.
    """
    return await service.create_product(payload, db, establishment)


@router.patch("/products/{product_id}", response_model=ReceptionProductResponse)
async def update_product(
    product_id: UUID,
    payload: ReceptionProductCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> ReceptionProductResponse:
    """Update a product's reception-relevant fields.

    Args:
        product_id (UUID): The product to update.
        payload (ReceptionProductCreate): Updated product data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ReceptionProductResponse: The updated product.
    """
    return await service.update_product(product_id, payload, db, establishment)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: UUID, db: DatabaseSession, establishment: CurrentSite) -> None:
    """Soft-delete a product from the reception catalog.

    Args:
        product_id (UUID): The product to deactivate.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.delete_product(product_id, db, establishment)


# ── Reception Sessions ────────────────────────────────────────────────────────


@router.post("/reception-sessions", response_model=ReceptionSessionResponse, status_code=201)
async def open_reception_session(
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
    s3: S3Dep,
    supplier_id: Annotated[UUID, Form()],
    received_at: Annotated[datetime, Form()],
    truck_condition_ok: Annotated[bool, Form()],
    packaging_integrity_ok: Annotated[bool, Form()],
    canned_goods_inspected_ok: Annotated[bool, Form()],
    bl_photo: Annotated[UploadFile | None, File()] = None,
    lab_report_photo: Annotated[UploadFile | None, File()] = None,
) -> ReceptionSessionResponse:
    """Open a new reception session for a supplier delivery.

    Uses multipart form data to support the optional BL photo alongside the
    structured fields.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.
        s3 (S3Dep): Injected S3 service for BL photo upload.
        supplier_id (UUID): The delivering supplier (form field).
        received_at (datetime): Operator-supplied delivery timestamp (form field).
        bl_photo (UploadFile | None): Optional delivery-note photo (file field).

    Returns:
        ReceptionSessionResponse: The created session with BL photo URL.
    """
    payload = ReceptionSessionCreate(
        supplier_id=supplier_id,
        received_at=received_at,
        truck_condition_ok=truck_condition_ok,
        packaging_integrity_ok=packaging_integrity_ok,
        canned_goods_inspected_ok=canned_goods_inspected_ok,
    )
    return await service.open_session(
        payload, db, establishment, operator, bl_photo, lab_report_photo, s3
    )


@router.get("/reception-sessions/{session_id}", response_model=ReceptionSessionDetailResponse)
async def get_reception_session(
    session_id: UUID, db: DatabaseSession, establishment: CurrentSite, s3: S3Dep
) -> ReceptionSessionDetailResponse:
    """Load a reception session with all its scanned item lines.

    Args:
        session_id (UUID): The session primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        s3 (S3Dep): Injected S3 service for BL photo URL construction.

    Returns:
        ReceptionSessionDetailResponse: Session detail including item lines.
    """
    return await service.get_session(session_id, db, establishment, s3)


@router.post(
    "/reception-sessions/{session_id}/items", response_model=ReceptionItemResponse, status_code=201
)
async def add_reception_item(
    session_id: UUID,
    payload: ReceptionItemCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> ReceptionItemResponse:
    """Scan a product line into an open reception session.

    Temperature compliance is re-validated server-side.  A non-conformity
    ticket is automatically opened when ``is_compliant = False``.

    Args:
        session_id (UUID): The target session.
        payload (ReceptionItemCreate): Scanned item data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        ReceptionItemResponse: The created reception item.
    """
    return await service.add_item(session_id, payload, db, establishment, operator)


@router.patch("/reception-sessions/{session_id}/close", response_model=ReceptionSessionResponse)
async def close_reception_session(
    session_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> ReceptionSessionResponse:
    """Close a reception session, preventing further item additions.

    Args:
        session_id (UUID): The session to close.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        ReceptionSessionResponse: The closed session.

    Raises:
        HTTPException: 409 Conflict if the session is already closed.
    """
    return await service.close_session(session_id, db, establishment)
