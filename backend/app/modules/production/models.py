"""ORM models for the Production domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.tenant.models import Etablissement


class BatchStatut(StrEnum):
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"


class FoodType(StrEnum):
    VOLAILLE = "VOLAILLE"
    VIANDE_HACHEE = "VIANDE_HACHEE"
    VIANDE_PIECE = "VIANDE_PIECE"
    LEGUMES_FECULENTS = "LEGUMES_FECULENTS"
    POISSON = "POISSON"
    AUTRE = "AUTRE"


class StepType(StrEnum):
    CUISSON_A_COEUR = "CUISSON_A_COEUR"
    REFROIDISSEMENT_DEBUT = "REFROIDISSEMENT_DEBUT"
    REFROIDISSEMENT_FIN = "REFROIDISSEMENT_FIN"


class ProductionBatch(TimestampMixin, Base):
    """A HACCP production batch grouping all cooking / cooling steps for one recipe.

    Now inherits ``TimestampMixin`` to record ``created_at`` / ``updated_at``
    for full audit-trail compliance.  The optional ``created_by_id`` FK
    attributes the batch creation to a specific operator — required for
    traceability when multiple staff share a tablet.
    """

    __tablename__ = "production_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nom_recette: Mapped[str] = mapped_column(String(255), nullable=False)
    food_type: Mapped[FoodType] = mapped_column(
        Enum(FoodType, name="production_food_type", native_enum=True),
        nullable=False,
        default=FoodType.AUTRE,
        server_default=FoodType.AUTRE.value,
    )
    date_production: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[BatchStatut] = mapped_column(
        Enum(BatchStatut, name="production_batch_statut", native_enum=True),
        nullable=False,
        default=BatchStatut.EN_COURS,
        server_default=BatchStatut.EN_COURS.value,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    etablissement: Mapped[Etablissement] = relationship("Etablissement", lazy="noload")
    steps: Mapped[list[ProductionStep]] = relationship(
        "ProductionStep",
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    ingredients: Mapped[list[ProductionBatchIngredient]] = relationship(
        "ProductionBatchIngredient",
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class ProductionStep(Base):
    """A single temperature measurement step within a production batch.

    ``temperature_mesuree`` uses ``Numeric(6, 2)`` (exact decimal) instead of
    ``Float`` (binary floating point) to prevent IEEE 754 rounding errors that
    could cause a legitimate 74.0°C reading to be stored as 73.9999… and
    incorrectly trigger a non-conformity alert for poultry.
    """

    __tablename__ = "production_steps"
    __table_args__ = (
        CheckConstraint(
            "temperature_mesuree BETWEEN -50 AND 300",
            name="production_step_temperature_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[StepType] = mapped_column(
        Enum(StepType, name="production_step_type", native_enum=True),
        nullable=False,
    )
    temperature_mesuree: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    batch: Mapped[ProductionBatch] = relationship("ProductionBatch", back_populates="steps")


class ProductionBatchIngredient(TimestampMixin, Base):
    """Traceability link between a production batch and a reception lot.

    This junction table implements the "one step backward / one step forward"
    traceability requirement of Regulation (EC) No. 178/2002.  It answers:

    - **Downstream**: "Which batches were made using lot X?" — find all rows
      where ``reception_item_id`` matches the recalled lot.
    - **Upstream**: "Which lots went into batch Y?" — find all rows where
      ``batch_id`` matches the batch.

    Both FKs use ``RESTRICT`` on delete, which makes it impossible to delete
    either the source ``ReceptionItem`` or the ``ProductionBatch`` while a
    traceability link exists — enforcing lot immutability at the database level.
    """

    __tablename__ = "production_batch_ingredients"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "reception_item_id",
            name="uq_production_batch_ingredients_batch_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reception_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reception_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_used: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)

    batch: Mapped[ProductionBatch] = relationship(
        "ProductionBatch", back_populates="ingredients"
    )
