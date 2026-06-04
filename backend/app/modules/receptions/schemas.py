"""
Pydantic schemas for the Receptions domain.

Covers two groups:

1. **Session schemas** — ``ReceptionSessionCreate``, ``ReceptionSessionResponse``,
   and ``ReceptionSessionDetailResponse`` (which extends the base response with
   the list of scanned items).  The ``bl_photo_url`` field carries a public URL
   built from the stored S3 key at read time; it is never persisted.

2. **Item schemas** — ``ReceptionItemCreate`` and ``ReceptionItemResponse``
   for individual product scan lines within a session.

``ReceptionItemCreate`` includes a ``@model_validator`` that catches a
logical inconsistency: an item cannot be marked compliant when its measured
temperature is out of the product's allowed range.  The ``product_min_temp``
and ``product_max_temp`` fields are ``exclude=True`` so they are never
serialised into the response — they are populated in the router from the
product catalog before validation runs.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.receptions.models import ReceptionStatus


class ReceptionSessionCreate(BaseModel):
    """Request body for opening a new reception session.

    The delivery timestamp and BL photo are submitted as form fields (not
    JSON) in the router to support the multipart photo upload.  This schema
    is constructed programmatically in the router from the parsed form values.

    Attributes:
        supplier_id (UUID): The delivering supplier.
        received_at (datetime): Operator-supplied delivery timestamp. May be
            timezone-naive; the service normalises it to the site timezone.
    """

    supplier_id: UUID
    received_at: datetime


class ReceptionSessionResponse(BaseModel):
    """Response body for a reception session (without item lines).

    The ``bl_photo_url`` is built from the stored S3 key by the
    ``_session_response`` helper at read time and is ``None`` when no photo
    was taken or when the S3 service is not injected (e.g. during close).

    Attributes:
        id (UUID): Session primary key.
        establishment_id (UUID): Owning establishment.
        operator_id (UUID): Operator who opened the session.
        supplier_id (UUID): Delivering supplier.
        received_at (datetime): Operator-supplied delivery timestamp.
        bl_photo_url (str | None): Public URL for the BL photo.
        status (ReceptionStatus): OPEN or CLOSED.
        opened_at (datetime): Server-side session creation timestamp.
        closed_at (datetime | None): When the session was closed.
    """

    model_config = {"from_attributes": True}

    id: UUID
    establishment_id: UUID
    operator_id: UUID
    supplier_id: UUID
    received_at: datetime
    bl_photo_url: str | None = None
    status: ReceptionStatus
    opened_at: datetime
    closed_at: datetime | None


class ReceptionItemResponse(BaseModel):
    """Response body for a single scanned reception item.

    Attributes:
        id (UUID): Item primary key.
        session_id (UUID): Owning session.
        product_id (UUID): Scanned product.
        lot_number (str): Batch/lot identifier.
        dluo (date): Use-by date.
        measured_temperature (float | None): Measured reception temperature.
        is_compliant (bool): Whether the item passed all reception checks.
        nc_id (UUID | None): Linked non-conformity ticket, if any.
        scanned_at (datetime): Site-local scan timestamp.
    """

    model_config = {"from_attributes": True}

    id: UUID
    session_id: UUID
    product_id: UUID
    lot_number: str
    dluo: date
    measured_temperature: float | None
    is_compliant: bool
    nc_id: UUID | None
    scanned_at: datetime


class ReceptionSessionDetailResponse(ReceptionSessionResponse):
    """Extended session response that includes the scanned item lines.

    Attributes:
        items (list[ReceptionItemResponse]): Scanned items ordered by
            ``scanned_at`` ascending.
    """

    items: list[ReceptionItemResponse] = []


class ReceptionItemCreate(BaseModel):
    """Request body for adding a scanned product line to an open session.

    The ``product_min_temp`` and ``product_max_temp`` fields are excluded
    from serialisation (``exclude=True``).  They are injected by the service
    layer from the product catalog record before the model validator runs, to
    catch the case where the operator marks a temperature-out-of-range item
    as compliant.

    Attributes:
        product_id (UUID): The scanned product.
        lot_number (str): Batch/lot identifier (1–64 chars).
        dluo (date): Use-by date.
        measured_temperature (float | None): Optional temperature reading.
        is_compliant (bool): Whether the operator considers the item acceptable.
        product_min_temp (float | None): Injected lower threshold (not serialised).
        product_max_temp (float | None): Injected upper threshold (not serialised).
    """

    product_id: UUID
    lot_number: str = Field(min_length=1, max_length=64)
    dluo: date
    measured_temperature: float | None = None
    is_compliant: bool
    product_min_temp: float | None = Field(default=None, exclude=True)
    product_max_temp: float | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_temperature_compliance(self) -> "ReceptionItemCreate":
        """Reject items marked compliant when temperature is out of range.

        When all three values are present (measured temperature + both thresholds),
        an item cannot be flagged ``is_compliant = True`` if the temperature falls
        outside the product's allowed range.  This prevents operators from
        accidentally accepting non-compliant cold-chain products.

        Returns:
            ReceptionItemCreate: The validated model instance.

        Raises:
            ValueError: If the temperature is out of range but ``is_compliant``
                is ``True``.
        """
        if (
            self.measured_temperature is not None
            and self.product_min_temp is not None
            and self.product_max_temp is not None
        ):
            in_range = self.product_min_temp <= self.measured_temperature <= self.product_max_temp
            if not in_range and self.is_compliant:
                raise ValueError(
                    "is_compliant doit être False : température hors des limites cibles."
                )
        return self
