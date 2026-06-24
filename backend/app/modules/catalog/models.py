"""
ORM models for the Catalog domain (Suppliers and Products).

This module defines the two core entities of the product catalog:

- ``Supplier`` — a food supplier subject to sanitary approval tracking.
  Each supplier record is scoped to one establishment and carries approval
  status, contact information, and optional certification metadata.

- ``Product`` — a catalog entry that links a food product to its supplier
  and encodes HACCP-relevant reception rules, most importantly whether the
  product requires a temperature check at delivery.

Both models use soft deletion (``is_active = False``) to preserve the
traceability of historical reception records even after a supplier or product
is retired from active use.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin


class SupplierCountry(StrEnum):
    """Enumeration of countries supported for supplier registration.

    Used to drive the SIRET validation rule: French suppliers must supply a
    14-character SIRET number, while foreign suppliers use their own national
    identifier format.
    """

    FRANCE = "France"
    BELGIQUE = "Belgique"
    SUISSE = "Suisse"
    LUXEMBOURG = "Luxembourg"
    ALLEMAGNE = "Allemagne"
    ESPAGNE = "Espagne"
    ITALIE = "Italie"
    PAYS_BAS = "Pays-Bas"
    ROYAUME_UNI = "Royaume-Uni"
    AUTRE = "Autre"


class SupplierStatus(StrEnum):
    """Approval lifecycle states for a supplier.

    French food-safety regulations require establishments to maintain a register
    of approved suppliers.  This enum models the full approval workflow:

    - ``PENDING`` — awaiting review.
    - ``APPROVED`` — cleared for deliveries.
    - ``REJECTED`` — failed sanitary review; deliveries should not be accepted.
    - ``OCCASIONAL`` — authorised for one-off deliveries only.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OCCASIONAL = "occasional"


class Supplier(TimestampMixin, Base):
    """A food supplier registered for one establishment with full sanitary tracking.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment. Indexed for
            multi-tenant query performance.
        name (str): Supplier trade name.
        company_registration_id (str | None): SIRET (France) or equivalent national
            registration number.
        country (SupplierCountry): Country of registration, used by schema validators
            to enforce SIRET format for French suppliers.
        address (str | None): Street address.
        city (str | None): City.
        postal_code (str | None): Postal/ZIP code.
        contact_name (str | None): Primary contact person.
        contact_email (str | None): Primary contact email.
        contact_phone (str | None): Primary contact phone.
        emergency_contact_name (str | None): On-call emergency contact name.
        emergency_phone (str | None): Emergency phone number, displayed prominently
            during a non-conformity incident.
        status (SupplierStatus): Current approval status.
        approval_date (datetime | None): Date of the most recent approval decision.
        certification_type (str | None): Free-text certification label (e.g. IFS, BRC).
        internal_notes (str | None): Manager-facing private notes.
        is_active (bool): Soft-delete flag.
    """

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_registration_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[SupplierCountry] = mapped_column(
        Enum(
            SupplierCountry,
            name="supplier_country",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=SupplierCountry.FRANCE,
    )
    address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[SupplierStatus] = mapped_column(
        Enum(
            SupplierStatus,
            name="supplier_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=SupplierStatus.PENDING,
        server_default="pending",
    )
    approval_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certification_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class Product(TimestampMixin, Base):
    """A catalog entry linking a food product to its supplier with HACCP reception rules.

    Every product belongs to exactly one supplier (enforced by a NOT NULL FK
    with RESTRICT on delete) and one establishment.  The ``has_temperature_control``
    flag drives the reception workflow: when ``True``, the operator must record a
    measured temperature and the system validates it against ``min_temperature``
    and ``max_temperature``.

    The ``gtin`` field stores the product's barcode (EAN-13, GS1) for the
    planned Scan & Go reception feature, allowing operators to scan a barcode
    instead of searching the catalog manually.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment.
        supplier_id (UUID): FK to the supplier. RESTRICT on delete prevents
            removing a supplier that still has active products.
        name (str): Product display name (e.g. "Steak Haché 15%").
        internal_reference (str | None): Internal SKU or reference code.
        gtin (str | None): Global Trade Item Number (barcode). Indexed for
            fast lookup during Scan & Go reception.
        has_temperature_control (bool): Whether this product requires a cold-chain
            temperature check at reception.
        min_temperature (float | None): Minimum acceptable delivery temperature in
            Celsius. ``None`` when ``has_temperature_control`` is ``False``.
        max_temperature (float | None): Maximum acceptable delivery temperature in
            Celsius. ``None`` when ``has_temperature_control`` is ``False``.
        is_active (bool): Soft-delete flag. Inactive products are hidden from
            the reception interface but their history is preserved.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    has_temperature_control: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    min_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    shelf_life_after_opening_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
