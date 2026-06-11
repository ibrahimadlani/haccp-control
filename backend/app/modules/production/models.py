"""ORM models for the Production domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base

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


class ProductionBatch(Base):
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

    etablissement: Mapped[Etablissement] = relationship("Etablissement", lazy="noload")
    steps: Mapped[list[ProductionStep]] = relationship(
        "ProductionStep",
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class ProductionStep(Base):
    __tablename__ = "production_steps"

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
    temperature_mesuree: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    batch: Mapped[ProductionBatch] = relationship("ProductionBatch", back_populates="steps")
