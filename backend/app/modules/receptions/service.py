"""
Business logic for the Receptions domain.

Manages the full delivery reception workflow:

**Products** — thin wrappers around the catalog service's reception-context
product functions (``list_products``, ``create_product``, ``update_product``,
``delete_product``).  These are proxied here so the reception router has a
single import point.

**Sessions** — ``open_session`` creates a new ``ReceptionSession``,
optionally uploads a BL photo to S3, and normalises the delivery timestamp to
the establishment's local timezone.

``add_item`` adds a scanned product line to an open session.  It re-validates
temperature compliance server-side (even though the tablet schema also
validates it) and automatically creates a ``NonConformity`` ticket with
``workflow_type = RECEPTION`` when ``is_compliant = False``.

``close_session`` transitions the session to ``CLOSED`` and prevents further
items from being added.

Private helpers ``_get_session_in_scope`` and ``_session_response`` are
shared by all session operations for consistent tenant scoping and S3 URL
construction.
"""

from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.metrics import (
    NONCONFORMITIES_OPENED_TOTAL,
    RECEPTION_ITEMS_TOTAL,
    RECEPTION_SESSIONS_CLOSED_TOTAL,
    RECEPTION_SESSIONS_OPENED_TOTAL,
)
from app.core.s3 import S3Service
from app.core.time_utils import now_for_site
from app.modules.catalog import service as catalog_service
from app.modules.catalog.models import Product
from app.modules.catalog.schemas import (
    ReceptionProductCreate,
    ReceptionProductListResponse,
    ReceptionProductResponse,
)
from app.modules.nonconformities.models import NonConformity, NonConformityStatus, WorkflowType
from app.modules.personnel.models import Utilisateur
from app.modules.receptions.models import ReceptionItem, ReceptionSession, ReceptionStatus
from app.modules.receptions.schemas import (
    ReceptionItemCreate,
    ReceptionItemResponse,
    ReceptionSessionCreate,
    ReceptionSessionDetailResponse,
    ReceptionSessionResponse,
)

logger = structlog.get_logger(__name__)

# ── Products (reception context) ──────────────────────────────────────────────


async def list_products(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    supplier_id: UUID | None = None,
) -> ReceptionProductListResponse:
    """Return active products for the tablet reception workflow.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        supplier_id (UUID | None): Optional supplier filter.

    Returns:
        ReceptionProductListResponse: Active products sorted by name.
    """
    return await catalog_service.list_products_for_reception(db, establishment, supplier_id)


async def create_product(
    payload: ReceptionProductCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ReceptionProductResponse:
    """Create a product quickly during an active reception session.

    Args:
        payload (ReceptionProductCreate): Minimal product data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ReceptionProductResponse: The created product.
    """
    return await catalog_service.create_product_for_reception(payload, db, establishment)


async def update_product(
    product_id: UUID,
    payload: ReceptionProductCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ReceptionProductResponse:
    """Update a product's reception-relevant fields.

    Args:
        product_id (UUID): The product to update.
        payload (ReceptionProductCreate): Updated product data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ReceptionProductResponse: The updated product.
    """
    return await catalog_service.update_product_for_reception(
        product_id, payload, db, establishment
    )


async def delete_product(
    product_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Soft-delete a product from within the reception workflow.

    Args:
        product_id (UUID): The product to deactivate.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
    """
    return await catalog_service.soft_delete_product_for_reception(product_id, db, establishment)


# ── Reception Sessions ────────────────────────────────────────────────────────


async def open_session(
    payload: ReceptionSessionCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
    bl_photo: UploadFile | None,
    s3: S3Service,
) -> ReceptionSessionResponse:
    """Open a new reception session for a supplier delivery.

    If a BL photo is provided, it is uploaded to S3 under the ``bl-photos``
    prefix and only the object key is stored in the database.

    The ``received_at`` timestamp from the payload is normalised to the
    establishment's local timezone before storage.  Timezone-naive datetimes
    are assumed to be in the site's local timezone.

    Args:
        payload (ReceptionSessionCreate): Supplier ID and delivery timestamp.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The PIN-authenticated operator opening the session.
        bl_photo (UploadFile | None): Optional delivery-note photo.
        s3 (S3Service): S3 service for BL photo upload.

    Returns:
        ReceptionSessionResponse: The created session with BL photo URL.
    """
    bl_key: str | None = None
    if bl_photo is not None:
        bl_key = await s3.upload_image(bl_photo, prefix="bl-photos")

    site_tz = ZoneInfo(establishment.timezone)
    received_at = (
        payload.received_at.replace(tzinfo=site_tz)
        if payload.received_at.tzinfo is None
        else payload.received_at.astimezone(site_tz)
    )

    session = ReceptionSession(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        supplier_id=payload.supplier_id,
        received_at=received_at,
        bl_photo_s3_key=bl_key,
        opened_at=now_for_site(establishment.timezone),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    RECEPTION_SESSIONS_OPENED_TOTAL.inc()
    logger.info(
        "reception_session_opened",
        session_id=str(session.id),
        supplier_id=str(session.supplier_id),
        has_bl_photo=bl_key is not None,
    )
    return _session_response(session, s3)


async def get_session(
    session_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    s3: S3Service,
) -> ReceptionSessionDetailResponse:
    """Load a reception session with all its scanned items.

    Args:
        session_id (UUID): The session primary key.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        s3 (S3Service): S3 service for BL photo URL construction.

    Returns:
        ReceptionSessionDetailResponse: Session with items.

    Raises:
        HTTPException: 404 Not Found if the session is not in scope.
    """
    session = await _get_session_in_scope(db, establishment, session_id)
    resp = _session_response(session, s3)
    return ReceptionSessionDetailResponse(
        **resp.model_dump(),
        items=[ReceptionItemResponse.model_validate(i) for i in session.items],
    )


async def add_item(
    session_id: UUID,
    payload: ReceptionItemCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> ReceptionItemResponse:
    """Add a scanned product line to an open reception session.

    Server-side temperature compliance is re-validated regardless of the
    client payload to prevent acceptance of out-of-range items.  When
    ``is_compliant = False``, a ``NonConformity`` ticket is automatically
    created with ``workflow_type = RECEPTION`` in the same transaction.

    Args:
        session_id (UUID): The target session.
        payload (ReceptionItemCreate): Scanned item data.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator (Utilisateur): The PIN-authenticated operator scanning the item.

    Returns:
        ReceptionItemResponse: The created reception item.

    Raises:
        HTTPException: 404 Not Found if the session or product is not in scope.
        HTTPException: 409 Conflict if the session is already closed.
    """
    session = await _get_session_in_scope(db, establishment, session_id)

    if session.status == ReceptionStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible d'ajouter un article à une session clôturée.",
        )

    product_result = await db.execute(
        select(Product).where(
            Product.id == payload.product_id,
            Product.establishment_id == establishment.etablissement_id,
            Product.is_active.is_(True),
        )
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    is_compliant = payload.is_compliant
    # Re-validate cold-chain compliance server-side: the tablet may have sent
    # is_compliant=True for a temperature-controlled product that is actually
    # out of range (e.g. due to a UI bug or a manipulated request).
    if (
        product.has_temperature_control
        and payload.measured_temperature is not None
        and product.min_temperature is not None
        and product.max_temperature is not None
    ):
        in_range = (
            product.min_temperature <= payload.measured_temperature <= product.max_temperature
        )
        if not in_range:
            is_compliant = False

    nc_id: UUID | None = None
    if not is_compliant:
        nc = NonConformity(
            establishment_id=establishment.etablissement_id,
            workflow_type=WorkflowType.RECEPTION,
            status=NonConformityStatus.OPEN,
            source_record_id=None,
            opened_by_id=operator.id,
            opened_at=now_for_site(establishment.timezone),
        )
        db.add(nc)
        await db.flush()
        nc_id = nc.id
        # Also track the reception-triggered NC in the shared NC counter.
        NONCONFORMITIES_OPENED_TOTAL.labels(workflow_type="RECEPTION").inc()

    item = ReceptionItem(
        session_id=session_id,
        product_id=payload.product_id,
        lot_number=payload.lot_number,
        dluo=payload.dluo,
        measured_temperature=payload.measured_temperature,
        is_compliant=is_compliant,
        nc_id=nc_id,
        scanned_at=now_for_site(establishment.timezone),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    RECEPTION_ITEMS_TOTAL.labels(is_compliant=str(is_compliant).lower()).inc()
    logger.info(
        "reception_item_added",
        session_id=str(session_id),
        product_id=str(payload.product_id),
        is_compliant=is_compliant,
        nc_opened=nc_id is not None,
    )
    return ReceptionItemResponse.model_validate(item)


async def close_session(
    session_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ReceptionSessionResponse:
    """Close a reception session, preventing further items from being added.

    Args:
        session_id (UUID): The session to close.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ReceptionSessionResponse: The closed session (BL photo URL not included
            since no S3 service is needed at close time).

    Raises:
        HTTPException: 404 Not Found if the session is not in scope.
        HTTPException: 409 Conflict if the session is already closed.
    """
    session = await _get_session_in_scope(db, establishment, session_id)
    if session.status == ReceptionStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La session est déjà clôturée."
        )
    session.status = ReceptionStatus.CLOSED
    session.closed_at = now_for_site(establishment.timezone)
    await db.commit()
    await db.refresh(session)
    RECEPTION_SESSIONS_CLOSED_TOTAL.inc()
    logger.info("reception_session_closed", session_id=str(session_id))
    # S3 is not needed here — the response is used only to confirm the close,
    # not to display the BL photo.
    return _session_response(session, None)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_session_in_scope(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    session_id: UUID,
) -> ReceptionSession:
    """Load a reception session scoped to the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        session_id (UUID): The session's primary key.

    Returns:
        ReceptionSession: The matching session ORM instance.

    Raises:
        HTTPException: 404 Not Found if the session does not exist or belongs
            to a different establishment.
    """
    result = await db.execute(
        select(ReceptionSession).where(
            ReceptionSession.id == session_id,
            ReceptionSession.establishment_id == establishment.etablissement_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reception session not found."
        )
    return session


def _session_response(session: ReceptionSession, s3: S3Service | None) -> ReceptionSessionResponse:
    """Build a ``ReceptionSessionResponse`` DTO, constructing the BL photo URL if available.

    Args:
        session (ReceptionSession): The ORM session instance.
        s3 (S3Service | None): S3 service for URL construction. ``None`` when
            no photo URL is needed (e.g. at session close).

    Returns:
        ReceptionSessionResponse: The response DTO with optional photo URL.
    """
    bl_url = s3.object_url(session.bl_photo_s3_key) if s3 and session.bl_photo_s3_key else None
    return ReceptionSessionResponse(
        id=session.id,
        establishment_id=session.establishment_id,
        operator_id=session.operator_id,
        supplier_id=session.supplier_id,
        received_at=session.received_at,
        bl_photo_url=bl_url,
        status=session.status,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
    )
