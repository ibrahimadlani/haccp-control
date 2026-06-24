"""
Pydantic schemas for the Catalog domain (Suppliers and Products).

Covers three sub-domains:

1. **Suppliers** — create/update/read schemas for ``Supplier`` records.
   ``SupplierBase`` includes a ``@model_validator`` that enforces a 14-digit
   SIRET for French suppliers.  ``SupplierUpdate`` uses fully optional fields
   (PATCH semantics).

2. **Products** — create/update/read schemas for ``Product`` catalog entries.
   Temperature fields (``min_temperature``, ``max_temperature``) are required
   when ``has_temperature_control`` is ``True`` and are explicitly cleared to
   ``None`` when it is ``False``.

3. **Reception-context products** — a lightweight subset of the product
   schemas used by the reception module when operators quickly register a
   product during a delivery.  These schemas intentionally omit fields not
   relevant to the reception workflow (e.g. ``is_active``) to keep the
   tablet UI simple.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.modules.catalog.models import SupplierCountry, SupplierStatus

# ── Suppliers ─────────────────────────────────────────────────────────────────


class SupplierBase(BaseModel):
    """Shared fields for supplier create operations.

    Attributes:
        name (str): Supplier trade name.
        company_registration_id (str | None): SIRET (France) or equivalent.
        country (SupplierCountry): Country of registration. Defaults to France.
        address (str | None): Street address.
        city (str | None): City.
        postal_code (str | None): Postal/ZIP code.
        contact_name (str | None): Primary contact person.
        contact_email (EmailStr | None): Primary contact email.
        contact_phone (str | None): Primary contact phone number.
        emergency_contact_name (str | None): On-call emergency contact name.
        emergency_phone (str | None): Emergency phone number.
        status (SupplierStatus): Approval lifecycle status. Defaults to PENDING.
        approval_date (datetime | None): Date of the most recent approval decision.
        certification_type (str | None): Free-text certification label (e.g. IFS, BRC).
        internal_notes (str | None): Manager-facing private notes.
    """

    name: str
    company_registration_id: str | None = None
    country: SupplierCountry = SupplierCountry.FRANCE
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_phone: str | None = None
    status: SupplierStatus = SupplierStatus.PENDING
    approval_date: datetime | None = None
    certification_type: str | None = None
    internal_notes: str | None = None

    @model_validator(mode="after")
    def validate_french_siret(self) -> "SupplierBase":
        """Enforce a 14-digit SIRET when the supplier is registered in France.

        Non-French suppliers may use any registration ID format.  Spaces are
        stripped before the length check to accommodate formatted input like
        ``"123 456 789 01234"``.

        Returns:
            SupplierBase: The validated model instance.

        Raises:
            ValueError: If the supplier is French and the SIRET does not
                contain exactly 14 non-space characters.
        """
        if self.country == SupplierCountry.FRANCE and self.company_registration_id is not None:
            clean = self.company_registration_id.replace(" ", "")
            if len(clean) != 14:
                raise ValueError(
                    "Le SIRET doit contenir exactement 14 caractères pour un fournisseur français."
                )
        return self


class SupplierCreate(SupplierBase):
    """Request body for creating a new supplier. Inherits all fields from ``SupplierBase``."""

    pass


class SupplierUpdate(BaseModel):
    """Request body for partially updating a supplier (PATCH semantics).

    All fields are optional — only supplied fields are applied.  The SIRET
    validation rule from ``SupplierBase`` is reproduced here because ``SupplierUpdate``
    does not inherit from it.

    Attributes:
        name (str | None): New trade name.
        company_registration_id (str | None): New registration ID.
        country (SupplierCountry | None): New country of registration.
        address (str | None): New street address.
        city (str | None): New city.
        postal_code (str | None): New postal code.
        contact_name (str | None): New primary contact.
        contact_email (EmailStr | None): New contact email.
        contact_phone (str | None): New contact phone.
        emergency_contact_name (str | None): New emergency contact name.
        emergency_phone (str | None): New emergency phone number.
        status (SupplierStatus | None): New approval status.
        approval_date (datetime | None): New approval date.
        certification_type (str | None): New certification label.
        internal_notes (str | None): Updated manager notes.
        is_active (bool | None): Soft-delete toggle. Set to ``False`` to deactivate.
    """

    name: str | None = None
    company_registration_id: str | None = None
    country: SupplierCountry | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_phone: str | None = None
    status: SupplierStatus | None = None
    approval_date: datetime | None = None
    certification_type: str | None = None
    internal_notes: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_french_siret(self) -> "SupplierUpdate":
        """Enforce 14-digit SIRET when country is updated to France.

        Returns:
            SupplierUpdate: The validated model instance.

        Raises:
            ValueError: If country is France and SIRET length is invalid.
        """
        if self.country == SupplierCountry.FRANCE and self.company_registration_id is not None:
            clean = self.company_registration_id.replace(" ", "")
            if len(clean) != 14:
                raise ValueError(
                    "Le SIRET doit contenir exactement 14 caractères pour un fournisseur français."
                )
        return self


class SupplierResponse(BaseModel):
    """Full supplier representation returned by read and write endpoints.

    Attributes:
        id (UUID): Supplier primary key.
        establishment_id (UUID): Owning establishment.
        name (str): Trade name.
        company_registration_id (str | None): SIRET or equivalent.
        country (SupplierCountry): Country of registration.
        address (str | None): Street address.
        city (str | None): City.
        postal_code (str | None): Postal code.
        contact_name (str | None): Primary contact person.
        contact_email (str | None): Primary contact email.
        contact_phone (str | None): Primary contact phone.
        emergency_contact_name (str | None): Emergency contact name.
        emergency_phone (str | None): Emergency phone number.
        status (SupplierStatus): Approval lifecycle status.
        approval_date (datetime | None): Most recent approval date.
        certification_type (str | None): Certification label.
        internal_notes (str | None): Manager-facing notes.
        is_active (bool): Whether the supplier is active.
        created_at (datetime): Record creation timestamp.
        updated_at (datetime): Last modification timestamp.
    """

    model_config = {"from_attributes": True}

    id: UUID
    establishment_id: UUID
    name: str
    company_registration_id: str | None
    country: SupplierCountry
    address: str | None
    city: str | None
    postal_code: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    emergency_contact_name: str | None
    emergency_phone: str | None
    status: SupplierStatus
    approval_date: datetime | None
    certification_type: str | None
    internal_notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    """Paginated list wrapper for supplier list endpoints.

    Attributes:
        items (list[SupplierResponse]): Supplier records sorted by name.
        total (int): Total count of matching suppliers.
    """

    items: list[SupplierResponse]
    total: int


# ── Products ──────────────────────────────────────────────────────────────────


class ProductBase(BaseModel):
    """Shared fields and temperature-control validation for product schemas.

    When ``has_temperature_control`` is ``True``, both ``min_temperature`` and
    ``max_temperature`` are required and ``min`` must be ≤ ``max``.  When it
    is ``False``, both temperature fields are forced to ``None`` regardless of
    what was supplied.

    Attributes:
        name (str): Product display name (1–255 chars).
        supplier_id (UUID): The owning supplier's primary key.
        internal_reference (str | None): Internal SKU (up to 128 chars).
        gtin (str | None): Global Trade Item Number barcode (up to 128 chars).
        has_temperature_control (bool): Whether cold-chain checks are required
            at reception. Defaults to ``False``.
        min_temperature (float | None): Lower bound of the safe reception
            temperature in Celsius. Required when ``has_temperature_control`` is
            ``True``.
        max_temperature (float | None): Upper bound. Required when
            ``has_temperature_control`` is ``True``.
    """

    name: str = Field(min_length=1, max_length=255)
    supplier_id: UUID
    internal_reference: str | None = Field(default=None, max_length=128)
    gtin: str | None = Field(default=None, max_length=128)
    has_temperature_control: bool = False
    min_temperature: float | None = None
    max_temperature: float | None = None
    shelf_life_after_opening_days: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_temperature_control(self) -> "ProductBase":
        """Enforce temperature field requirements based on ``has_temperature_control``.

        Returns:
            ProductBase: The validated model instance.

        Raises:
            ValueError: If ``has_temperature_control`` is ``True`` but either
                temperature field is missing, or ``min`` > ``max``.
        """
        if self.has_temperature_control:
            if self.min_temperature is None or self.max_temperature is None:
                raise ValueError(
                    "min_temperature et max_temperature requis si has_temperature_control."
                )
            if self.min_temperature > self.max_temperature:
                raise ValueError("min_temperature doit être inférieur ou égal à max_temperature.")
        else:
            # Clear temperature fields to prevent inconsistent state where
            # temperatures are stored but cold-chain flag is disabled.
            self.min_temperature = None
            self.max_temperature = None
        return self


class ProductCreate(ProductBase):
    """Request body for creating a new catalog product. Inherits all fields from ``ProductBase``."""

    pass


class ProductUpdate(BaseModel):
    """Request body for partially updating a catalog product (PATCH semantics).

    All fields are optional.  Temperature validation mirrors ``ProductBase``
    but only triggers when ``has_temperature_control`` is explicitly supplied.

    Attributes:
        name (str | None): New product name.
        supplier_id (UUID | None): New supplier.
        internal_reference (str | None): New SKU.
        gtin (str | None): New barcode.
        has_temperature_control (bool | None): New cold-chain flag.
        min_temperature (float | None): New minimum reception temperature.
        max_temperature (float | None): New maximum reception temperature.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    supplier_id: UUID | None = None
    internal_reference: str | None = Field(default=None, max_length=128)
    gtin: str | None = Field(default=None, max_length=128)
    has_temperature_control: bool | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None
    shelf_life_after_opening_days: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_temperature_control(self) -> "ProductUpdate":
        """Apply temperature validation when the cold-chain flag is being changed.

        Returns:
            ProductUpdate: The validated model instance.

        Raises:
            ValueError: If ``has_temperature_control=True`` but temperature
                fields are missing, or ``min > max``.
        """
        if self.has_temperature_control is True:
            if self.min_temperature is None or self.max_temperature is None:
                raise ValueError(
                    "min_temperature et max_temperature requis si has_temperature_control."
                )
            if self.min_temperature > self.max_temperature:
                raise ValueError("min_temperature doit être inférieur ou égal à max_temperature.")
        if self.has_temperature_control is False:
            self.min_temperature = None
            self.max_temperature = None
        return self


class ProductResponse(BaseModel):
    """Full product representation returned by read and write endpoints.

    Attributes:
        id (UUID): Product primary key.
        establishment_id (UUID): Owning establishment.
        supplier_id (UUID): Owning supplier.
        name (str): Product display name.
        internal_reference (str | None): Internal SKU.
        gtin (str | None): Barcode.
        has_temperature_control (bool): Cold-chain flag.
        min_temperature (float | None): Minimum acceptable reception temperature.
        max_temperature (float | None): Maximum acceptable reception temperature.
        is_active (bool): Soft-delete flag.
        created_at (datetime): Record creation timestamp.
        updated_at (datetime): Last modification timestamp.
    """

    model_config = {"from_attributes": True}

    id: UUID
    establishment_id: UUID
    supplier_id: UUID
    name: str
    internal_reference: str | None
    gtin: str | None
    has_temperature_control: bool
    min_temperature: float | None
    max_temperature: float | None
    shelf_life_after_opening_days: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated list wrapper for catalog product list endpoints.

    Attributes:
        items (list[ProductResponse]): Product records sorted by name.
        total (int): Total count of matching products.
    """

    items: list[ProductResponse]
    total: int


# ── Reception-context product schemas (used by receptions module) ─────────────


class ReceptionProductCreate(BaseModel):
    """Request body for quickly creating a product during a reception session.

    Simplified version of ``ProductCreate`` for the tablet workflow where
    operators register previously unseen products on the fly.  The supplier
    is optional to allow anonymous product entries.

    Attributes:
        name (str): Product display name (1–255 chars).
        internal_reference (str | None): Optional SKU.
        supplier_id (UUID | None): Optional supplier. ``None`` for unknown suppliers.
        has_temperature_control (bool): Cold-chain flag. Defaults to ``False``.
        min_temperature (float | None): Required when ``has_temperature_control=True``.
        max_temperature (float | None): Required when ``has_temperature_control=True``.
            Must be strictly greater than ``min_temperature``.
    """

    name: str = Field(min_length=1, max_length=255)
    internal_reference: str | None = Field(default=None, max_length=128)
    supplier_id: UUID | None = None
    has_temperature_control: bool = False
    min_temperature: float | None = None
    max_temperature: float | None = None

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "ReceptionProductCreate":
        """Enforce temperature range when cold-chain control is enabled.

        Uses strict inequality (min < max) rather than ≤ used in ``ProductBase``
        to prevent zero-width ranges that would make every reading non-compliant.

        Returns:
            ReceptionProductCreate: The validated model instance.

        Raises:
            ValueError: If temperatures are missing or ``min >= max``.
        """
        if self.has_temperature_control:
            if self.min_temperature is None or self.max_temperature is None:
                raise ValueError(
                    "min_temperature et max_temperature requis si has_temperature_control est True."
                )
            if self.min_temperature >= self.max_temperature:
                raise ValueError(
                    "min_temperature doit être strictement inférieur à max_temperature."
                )
        return self


class ReceptionProductResponse(BaseModel):
    """Compact product representation for the reception tablet workflow.

    Excludes ``is_active``, ``gtin``, and audit timestamps to keep the
    reception screen payload minimal.

    Attributes:
        id (UUID): Product primary key.
        establishment_id (UUID): Owning establishment.
        supplier_id (UUID): Owning supplier.
        name (str): Product display name.
        internal_reference (str | None): Internal SKU.
        has_temperature_control (bool): Cold-chain flag.
        min_temperature (float | None): Minimum acceptable temperature.
        max_temperature (float | None): Maximum acceptable temperature.
    """

    model_config = {"from_attributes": True}

    id: UUID
    establishment_id: UUID
    supplier_id: UUID
    name: str
    internal_reference: str | None
    has_temperature_control: bool
    min_temperature: float | None
    max_temperature: float | None
    shelf_life_after_opening_days: int | None


class ReceptionProductListResponse(BaseModel):
    """Paginated list wrapper for the reception product list endpoint.

    Attributes:
        items (list[ReceptionProductResponse]): Products sorted by name.
        total (int): Total count.
    """

    items: list[ReceptionProductResponse]
    total: int
