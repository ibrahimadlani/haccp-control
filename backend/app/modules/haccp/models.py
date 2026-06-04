"""
ORM models for the HACCP (Hazard Analysis and Critical Control Points) domain.

This module defines the core data capture models for HACCP compliance:

- ``ReleveTemperature`` — a single temperature measurement recorded at a
  critical control point (CCP).  If the measured value falls outside the
  equipment's target range, a ``NonConformity`` ticket is automatically opened.

- ``Pointage`` — an HR time-clock event (clock in/out, break start/end)
  recorded by an operator on the shared establishment tablet.

Both models reference entities from other domains (``Equipement``,
``Utilisateur``, ``Etablissement``) using string-based SQLAlchemy relationship
declarations to avoid circular module-level imports.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.equipments.models import Equipement
    from app.modules.nonconformities.models import NonConformity
    from app.modules.personnel.models import Utilisateur
    from app.modules.tenant.models import Etablissement


class SourceReleve(StrEnum):
    """Origin of a temperature measurement.

    Attributes:
        MANUEL: Reading entered manually by an operator on the tablet.
        IOT: Reading pushed automatically by an IoT sensor.
    """

    MANUEL = "MANUEL"
    IOT = "IOT"


class TypeEvenementPointage(StrEnum):
    """Type of a time-clock event recorded by an operator.

    The valid state-machine transitions are enforced in the HACCP service layer:
    ``CLOCKED_OUT → CLOCK_IN → BREAK_START ↔ BREAK_END → CLOCK_OUT``.
    """

    CLOCK_IN = "CLOCK_IN"
    BREAK_START = "BREAK_START"
    BREAK_END = "BREAK_END"
    CLOCK_OUT = "CLOCK_OUT"


class ReleveTemperature(TimestampMixin, Base):
    """A HACCP temperature record captured at one critical control point.

    Each record is linked to the equipment being monitored and the operator who
    took the reading.  The ``is_conforme`` flag is computed by the service layer
    at write time by comparing ``valeur_mesuree`` against the equipment's
    ``temperature_min_cible`` / ``temperature_max_cible`` thresholds.

    When ``is_conforme`` is ``False``, the service automatically creates a linked
    ``NonConformity`` ticket in the same transaction, enabling the corrective
    action workflow to start immediately.

    Attributes:
        id (UUID): Primary key.
        etablissement_id (UUID): FK to the establishment (multi-tenant filter).
        equipement_id (UUID): FK to the monitored equipment.
        utilisateur_id (UUID): FK to the operator who recorded the value.
        valeur_mesuree (Decimal): Measured temperature in Celsius (6 digits, 2 d.p.).
        is_conforme (bool): ``True`` if the value is within the equipment's target
            range. Computed at write time; never updated after creation.
        source (SourceReleve): Whether the reading was entered manually or via IoT.
        mesure_effectuee_at (datetime): Timezone-aware timestamp of when the
            measurement was taken, which may differ from ``created_at`` (the DB
            insertion time) when records are submitted with a delay.
        equipement (Equipement): Eagerly loaded equipment (for threshold checks).
        utilisateur (Utilisateur): Eagerly loaded operator (for audit display).
        nonconformity (NonConformity | None): The auto-opened non-conformity ticket,
            loaded lazily to avoid unnecessary joins on happy-path queries.
    """

    __tablename__ = "releves_temperature"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    valeur_mesuree: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_conforme: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[SourceReleve] = mapped_column(
        Enum(SourceReleve, name="source_releve", native_enum=True), nullable=False
    )
    mesure_effectuee_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # String-based relationship targets prevent circular module imports while
    # still allowing SQLAlchemy to resolve them via the mapper registry at startup.
    equipement: Mapped[Equipement] = relationship(
        "Equipement", back_populates="releves", lazy="selectin"
    )
    utilisateur: Mapped[Utilisateur] = relationship("Utilisateur", lazy="selectin")
    nonconformity: Mapped[NonConformity | None] = relationship(
        "NonConformity", back_populates="source_record", lazy="noload", uselist=False
    )


class Pointage(TimestampMixin, Base):
    """An HR time-clock event recorded by an operator on the shared tablet.

    Records form a chronological log per operator per establishment.  The
    HACCP service reads the latest event to determine the operator's current
    status (active, on break, clocked out) and validates that the new event
    represents a permitted state-machine transition before writing.

    Attributes:
        id (UUID): Primary key.
        etablissement_id (UUID): FK to the establishment.
        utilisateur_id (UUID): FK to the operator.
        type_evenement (TypeEvenementPointage): The clock event type.
        pointe_at (datetime): Timezone-aware timestamp of the event, computed
            using the establishment's configured timezone.
        etablissement (Etablissement): Eagerly loaded establishment.
        utilisateur (Utilisateur): Eagerly loaded operator.
    """

    __tablename__ = "pointages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type_evenement: Mapped[TypeEvenementPointage] = mapped_column(
        Enum(TypeEvenementPointage, name="type_evenement_pointage", native_enum=True),
        nullable=False,
    )
    pointe_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    etablissement: Mapped[Etablissement] = relationship("Etablissement", lazy="selectin")
    utilisateur: Mapped[Utilisateur] = relationship("Utilisateur", lazy="selectin")
