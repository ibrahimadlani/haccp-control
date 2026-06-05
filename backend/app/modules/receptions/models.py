"""
ORM models for the Receptions domain.

This module defines the two entities that model the supplier delivery
reception workflow:

- ``ReceptionSession`` — a dossier opened by an operator for one delivery
  note (BL).  It captures the supplier, the delivery date/time, and an
  optional photo of the BL.  A session is ``OPEN`` while the operator is
  scanning items and transitions to ``CLOSED`` when they confirm the
  reception is complete.

- ``ReceptionItem`` — one scanned product line within a session.  Carries
  the lot number, use-by date (DLUO), optional measured temperature,
  a packaging-integrity flag, and an overall compliance flag.  When
  ``is_compliant = False`` (temperature out of range, packaging damaged, or
  manually flagged), a ``NonConformity`` ticket is automatically created with
  ``workflow_type = RECEPTION``.

The ``bl_photo_s3_key`` column stores the S3 object key of the delivery-note
photo.  Public URLs are generated on the fly at read time by the
``_session_response`` helper in the service layer.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class ReceptionStatus(StrEnum):
    """Lifecycle status of a reception session.

    Attributes:
        OPEN: Session is in progress; items can still be added.
        CLOSED: Session has been confirmed; no further items can be added.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ReceptionSession(TimestampMixin, Base):
    """A supplier delivery reception dossier opened by an operator.

    Represents one delivery event (one BL) and groups all scanned product
    items for that delivery.  The ``received_at`` timestamp is supplied by
    the operator (the actual delivery time) while ``opened_at`` is the
    server-side time when the session was created.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment.
        operator_id (UUID): FK to the operator who opened the session.
            RESTRICT on delete preserves the audit trail.
        supplier_id (UUID): FK to the supplier. RESTRICT on delete.
        received_at (datetime): Operator-supplied delivery timestamp
            (timezone-aware, normalised to the establishment's local timezone).
        bl_photo_s3_key (str | None): S3 object key for the delivery-note photo.
            ``None`` when no photo was taken.
        truck_condition_ok (bool): Delivery vehicle was clean and at the correct
            temperature at arrival (a session-wide control per HACCP reception
            requirements). Defaults to ``True`` — operators only update it when
            a non-conformity is observed.
        status (ReceptionStatus): OPEN while in progress, CLOSED after confirmation.
        opened_at (datetime): Server-side session creation timestamp.
        closed_at (datetime | None): When the session was closed.
        items (list[ReceptionItem]): Scanned product lines, ordered by
            ``scanned_at`` ascending.
    """

    __tablename__ = "reception_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    bl_photo_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    truck_condition_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    status: Mapped[ReceptionStatus] = mapped_column(
        Enum(ReceptionStatus, name="reception_status", native_enum=True),
        nullable=False,
        default=ReceptionStatus.OPEN,
        server_default=text("'OPEN'"),
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[ReceptionItem]] = relationship(
        "ReceptionItem",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ReceptionItem.scanned_at",
    )


class ReceptionItem(TimestampMixin, Base):
    """One scanned product line within a reception session.

    Records what was received (product + lot + DLUO), the measured
    temperature (if the product requires cold-chain control), and whether
    the item is compliant.  A linked ``NonConformity`` FK is set when
    ``is_compliant = False`` so the dashboard can navigate from the item
    directly to the incident ticket.

    Attributes:
        id (UUID): Primary key.
        session_id (UUID): FK to the owning reception session. CASCADE on delete.
        product_id (UUID): FK to the product catalog entry. RESTRICT on delete.
        lot_number (str): Batch/lot identifier from the product label.
        dluo (date): Use-by date (Date de Limite d'Utilisation Optimale).
        measured_temperature (float | None): Measured reception temperature in
            Celsius. ``None`` when the product has no cold-chain requirement.
        packaging_ok (bool): Packaging was intact at reception — covers both
            general packaging integrity and bombage/swelling on canned goods
            (botulism indicator). Defaults to ``True``; set to ``False`` when
            any packaging defect is observed. Forces ``is_compliant = False``
            in the service layer.
        is_compliant (bool): Whether the item passed all reception checks.
            Set to ``False`` automatically when temperature is out of range or
            ``packaging_ok = False``.
        nc_id (UUID | None): FK to the non-conformity ticket opened for this
            item. ``None`` for compliant items. SET NULL on delete.
        scanned_at (datetime): Site-local timestamp of when the item was scanned.
        session (ReceptionSession): Back-reference to the owning session.
    """

    __tablename__ = "reception_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reception_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lot_number: Mapped[str] = mapped_column(String(128), nullable=False)
    dluo: Mapped[date] = mapped_column(Date, nullable=False)
    measured_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    packaging_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    nc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("non_conformities.id", ondelete="SET NULL"), nullable=True
    )
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ReceptionSession] = relationship(
        "ReceptionSession", back_populates="items", lazy="noload"
    )
