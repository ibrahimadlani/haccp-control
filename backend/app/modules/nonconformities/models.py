"""
ORM models for the Non-Conformities domain.

A non-conformity (NC) is a HACCP incident ticket that is opened automatically
when a critical control point measurement fails (e.g. a temperature out of
range) or manually when an operator spots a problem during a reception.

This module defines:

- ``NonConformity`` — the master ticket entity, tracking the full lifecycle
  from detection (``OPEN``) through acknowledgement (``IN_PROGRESS``), corrective
  action (``RESOLVED``), and manager sign-off (``CLOSED``).

- ``ActionCorrective`` — the corrective action record that an operator writes
  and signs (with an optional photo) to resolve an open non-conformity.

Both the ``WorkflowType`` and ``NonConformityStatus`` enums are kept in this
module because they model concepts that are specific to the NC domain, even
though ``WorkflowType`` is also referenced by ``ReleveTemperature`` via the
``ReceptionStatus`` relationship.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.haccp.models import ReleveTemperature
    from app.modules.personnel.models import Utilisateur


class WorkflowType(StrEnum):
    """Category of the HACCP workflow that generated a non-conformity.

    Attributes:
        TEMPERATURE: NC opened because a temperature record was out of range.
        RECEPTION: NC opened during a supplier delivery reception check.
    """

    TEMPERATURE = "TEMPERATURE"
    RECEPTION = "RECEPTION"


class NonConformityStatus(StrEnum):
    """Lifecycle states of a non-conformity ticket.

    The permitted transitions are:
    ``OPEN → IN_PROGRESS → RESOLVED → CLOSED``.

    - ``OPEN``: Automatically set when the NC is created.
    - ``IN_PROGRESS``: Set when an operator acknowledges the ticket.
    - ``RESOLVED``: Set when an operator submits a corrective action.
    - ``CLOSED``: Set by a manager after reviewing the corrective action.
    """

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class NonConformity(TimestampMixin, Base):
    """A HACCP incident ticket tracking the full corrective action lifecycle.

    Non-conformities are created automatically when a ``ReleveTemperature``
    record is out of range (linked via ``source_record_id``), or manually for
    other workflow types.  The ticket then follows a four-state lifecycle
    managed by the non-conformities service.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the establishment for multi-tenant isolation.
        workflow_type (WorkflowType): The HACCP workflow that originated the NC.
        status (NonConformityStatus): Current lifecycle state.
        source_record_id (UUID | None): FK to the offending ``ReleveTemperature``.
            ``None`` for manually opened or reception-triggered NCs.
        opened_by_id (UUID): FK to the operator who detected the problem.
        opened_at (datetime): When the NC was opened (equals ``mesure_effectuee_at``
            for temperature NCs, ``now()`` for manual ones).
        assigned_to_id (UUID | None): FK to the operator who acknowledged the NC.
        assigned_at (datetime | None): When the NC was acknowledged.
        resolved_at (datetime | None): When the corrective action was submitted.
        closed_by_id (UUID | None): FK to the manager who closed the NC.
        closed_at (datetime | None): When the manager closed the NC.
        closing_comment (str | None): Optional manager note written at closure.
        source_record (ReleveTemperature | None): The triggering temperature record.
        corrective_action (ActionCorrective | None): The signed corrective action.
        opened_by (Utilisateur): The operator who opened the NC.
        assigned_to (Utilisateur | None): The operator who acknowledged the NC.
        closed_by (Utilisateur | None): The manager who closed the NC.
    """

    __tablename__ = "non_conformities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflow_type", native_enum=True), nullable=False
    )
    status: Mapped[NonConformityStatus] = mapped_column(
        Enum(NonConformityStatus, name="nonconformity_status", native_enum=True),
        nullable=False,
        default=NonConformityStatus.OPEN,
        server_default=text("'OPEN'"),
    )
    # Unique constraint ensures each temperature record can trigger at most one NC.
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("releves_temperature.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
        index=True,
    )
    opened_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closing_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Explicit foreign_keys are required because there are three FKs to the same
    # Utilisateur table; SQLAlchemy cannot determine which FK backs which relationship
    # without the hint.
    source_record: Mapped[ReleveTemperature | None] = relationship(
        "ReleveTemperature",
        back_populates="nonconformity",
        lazy="selectin",
        foreign_keys=[source_record_id],
    )
    corrective_action: Mapped[ActionCorrective | None] = relationship(
        "ActionCorrective",
        back_populates="nonconformity",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    opened_by: Mapped[Utilisateur] = relationship(
        "Utilisateur", foreign_keys=[opened_by_id], lazy="selectin"
    )
    assigned_to: Mapped[Utilisateur | None] = relationship(
        "Utilisateur", foreign_keys=[assigned_to_id], lazy="selectin"
    )
    closed_by: Mapped[Utilisateur | None] = relationship(
        "Utilisateur", foreign_keys=[closed_by_id], lazy="selectin"
    )


class ActionCorrective(TimestampMixin, Base):
    """A corrective action signed by an operator to resolve a non-conformity.

    An ``ActionCorrective`` is always associated with exactly one
    ``NonConformity`` (enforced by the ``UNIQUE`` constraint on
    ``nonconformity_id``).  Submitting a corrective action automatically
    transitions the parent NC to ``RESOLVED``.

    The optional ``photo_s3_key`` stores the S3 object key of a photographic
    evidence upload, not a presigned URL.  Public URLs are generated on the fly
    by the S3 service when the NC is retrieved.

    Attributes:
        id (UUID): Primary key.
        nonconformity_id (UUID): FK to the parent ``NonConformity``. Unique.
        utilisateur_id (UUID): FK to the signing operator.
        description (str): Free-text description of the corrective action taken.
        photo_s3_key (str | None): S3 object key of the evidence photo, if any.
        signee_at (datetime): Timezone-aware timestamp of when the action was signed.
        nonconformity (NonConformity): The parent ticket.
        utilisateur (Utilisateur): The signing operator.
    """

    __tablename__ = "actions_correctives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nonconformity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("non_conformities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    signee_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    nonconformity: Mapped[NonConformity] = relationship(
        "NonConformity", back_populates="corrective_action", lazy="selectin"
    )
    utilisateur: Mapped[Utilisateur] = relationship(
        "Utilisateur", foreign_keys=[utilisateur_id], lazy="selectin"
    )
