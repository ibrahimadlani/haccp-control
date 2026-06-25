"""
Pydantic schemas for the Receptions domain.

Covers three groups:

1. **Session schemas** — ``ReceptionSessionCreate``, ``ReceptionSessionResponse``,
   and ``ReceptionSessionDetailResponse`` (which extends the base response with
   the list of scanned items).  The ``bl_photo_url`` field carries a public URL
   built from the stored S3 key at read time; it is never persisted.

2. **Item schemas** — ``ReceptionItemCreate`` and ``ReceptionItemResponse``
   for individual product scan lines within a session.

``ReceptionItemCreate`` includes a ``@model_validator`` that catches logical
inconsistencies: an item cannot be marked compliant when its measured
temperature is out of range, or when ``packaging_ok = False``.  The
``product_min_temp`` and ``product_max_temp`` fields are ``exclude=True`` so
they are never serialised — they are populated in the router from the catalog.

3. **Search schema** — ``ReceptionLotSearchItem`` for the lot-number recall
   search endpoint.

4. **Lot ouverture schemas** — ``LotOuvertureCreate`` / ``LotOuvertureResponse``
   model the HACCP workflow of opening a lot and computing its secondary DLC.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.receptions.models import ReceptionStatus, StatutOuverture


class ReceptionSessionCreate(BaseModel):
    """Request body for opening a new reception session.

    The delivery timestamp and BL photo are submitted as form fields (not
    JSON) in the router to support the multipart photo upload.  This schema
    is constructed programmatically in the router from the parsed form values.

    Attributes:
        supplier_id (UUID): The delivering supplier.
        received_at (datetime): Operator-supplied delivery timestamp. May be
            timezone-naive; the service normalises it to the site timezone.
        truck_condition_ok (bool): Delivery vehicle was clean and at correct
            temperature at arrival. Defaults to ``True``; set to ``False`` when
            the operator observes a vehicle non-conformity.
    """

    supplier_id: UUID
    received_at: datetime
    truck_condition_ok: bool = True


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
        truck_condition_ok (bool): Delivery vehicle conformity flag.
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
    truck_condition_ok: bool
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
        packaging_ok (bool): Packaging was intact at reception.
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
    packaging_ok: bool
    is_surgele: bool
    is_compliant: bool
    nc_id: UUID | None
    scanned_at: datetime


class ReceptionLotSearchItem(BaseModel):
    """Reception line matched by lot number for sanitary recall.

    Attributes:
        item_id (UUID): Reception item primary key.
        session_id (UUID): Owning session.
        lot_number (str): Matched batch/lot identifier.
        dluo (date): Use-by date of the matched item.
        product_id (UUID): Associated product.
        product_name (str | None): Product display name from catalog.
        received_at (datetime): Delivery timestamp of the session.
        packaging_ok (bool): Packaging integrity at reception.
        is_compliant (bool): Overall compliance of the item.
    """

    item_id: UUID
    session_id: UUID
    lot_number: str
    dluo: date
    product_id: UUID
    product_name: str | None = None
    received_at: datetime
    packaging_ok: bool
    is_compliant: bool


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
        packaging_ok (bool): Packaging was intact. Defaults to ``True``;
            set to ``False`` when any packaging defect is observed (torn,
            damaged, or swollen for canned goods). Forces ``is_compliant``
            to ``False`` via the model validator.
        is_compliant (bool): Whether the operator considers the item acceptable.
        product_min_temp (float | None): Injected lower threshold (not serialised).
        product_max_temp (float | None): Injected upper threshold (not serialised).
    """

    product_id: UUID
    lot_number: str = Field(min_length=1, max_length=64)
    dluo: date
    measured_temperature: float | None = None
    packaging_ok: bool = True
    is_surgele: bool = False
    is_compliant: bool
    product_min_temp: float | None = Field(default=None, exclude=True)
    product_max_temp: float | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_compliance(self) -> "ReceptionItemCreate":
        """Reject items marked compliant when temperature is out of range or packaging is damaged.

        Ensures ``is_compliant`` cannot be ``True`` when:
        - measured temperature is outside the product's allowed range, or
        - ``packaging_ok = False`` (damaged packaging or swollen canned goods).

        Returns:
            ReceptionItemCreate: The validated model instance.

        Raises:
            ValueError: If ``is_compliant`` is inconsistent with observed defects.
        """
        if not self.packaging_ok and self.is_compliant:
            raise ValueError("is_compliant doit être False : l'emballage est non conforme.")
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


# ── Lot ouverture (DLC secondaire) ────────────────────────────────────────────


class LotOuvertureCreate(BaseModel):
    """Request body for opening a reception lot and computing its secondary DLC.

    Attributes:
        duree_apres_ouverture_jours (int): Shelf life in days after the product
            is opened.  The service caps the computed secondary DLC at the lot's
            primary DLUO so this value can never extend the supplier's original
            expiry date.  Must be ≥ 1.
    """

    duree_apres_ouverture_jours: int = Field(ge=1)


class LotOuvertureResponse(BaseModel):
    """Response returned after a lot is opened.

    Attributes:
        id (UUID): Opening event primary key.
        establishment_id (UUID): Owning establishment.
        reception_item_id (UUID): Source reception item.
        operator_id (UUID): Operator who opened the lot.
        ouvert_at (datetime): Site-local timestamp of the opening.
        dluo_primaire (date): Supplier DLC/DDM (upper bound).
        duree_apres_ouverture_jours (int): Configured shelf life after opening.
        dlc_secondaire_calculee (date): Computed secondary DLC (≤ dluo_primaire).
        was_frozen (bool): Whether the product was frozen at opening.
        statut (StatutOuverture): Current lifecycle state of the opened lot.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    establishment_id: UUID
    reception_item_id: UUID
    operator_id: UUID
    ouvert_at: datetime
    dluo_primaire: date
    duree_apres_ouverture_jours: int
    dlc_secondaire_calculee: date
    was_frozen: bool
    statut: StatutOuverture


class LotOuvertureListResponse(BaseModel):
    """List of active (OUVERT) lot openings at an establishment."""

    items: list[LotOuvertureResponse]
