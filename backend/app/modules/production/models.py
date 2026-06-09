"""ORM models for production controls (cooking, hot holding) and witness samples."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin

# Seuil réglementaire restauration collective — cuisson / maintien au chaud.
MIN_HOT_TEMPERATURE_C = Decimal("63.00")
# Témoin polaire friteuse — changement d'huile si > 25 %.
MAX_POLAR_TEST_PERCENT = Decimal("25.00")


class ProductionControlType(StrEnum):
    """Type of in-kitchen temperature control during service."""

    COOKING_CORE = "COOKING_CORE"
    HOT_HOLDING = "HOT_HOLDING"


class MenuProteinType(StrEnum):
    """Type de protéine — détermine le seuil de cuisson à cœur (DGCCRF cantine)."""

    POULTRY = "POULTRY"
    MINCED_MEAT = "MINCED_MEAT"
    WHOLE_MEAT = "WHOLE_MEAT"
    FISH = "FISH"
    VEGETARIAN = "VEGETARIAN"
    OTHER = "OTHER"


# Seuils cuisson à cœur selon type de protéine (°C).
CORE_TEMP_BY_PROTEIN: dict[MenuProteinType, Decimal] = {
    MenuProteinType.POULTRY: Decimal("75.00"),
    MenuProteinType.MINCED_MEAT: Decimal("75.00"),
    MenuProteinType.WHOLE_MEAT: Decimal("63.00"),
    MenuProteinType.FISH: Decimal("63.00"),
    MenuProteinType.VEGETARIAN: Decimal("63.00"),
    MenuProteinType.OTHER: Decimal("63.00"),
}


class ProductionTemperatureRecord(TimestampMixin, Base):
    """Temperature at core or during hot holding for a prepared dish."""

    __tablename__ = "production_temperature_records"

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
    dish_name: Mapped[str] = mapped_column(String(255), nullable=False)
    control_type: Mapped[ProductionControlType] = mapped_column(
        Enum(ProductionControlType, name="production_control_type", native_enum=True),
        nullable=False,
    )
    measured_value: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    min_required_c: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=MIN_HOT_TEMPERATURE_C
    )
    is_conforme: Mapped[bool] = mapped_column(Boolean, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WitnessSample(TimestampMixin, Base):
    """Plat témoin — échantillon conservé 5 jours au frais (restauration collective)."""

    __tablename__ = "witness_samples"

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
    dish_name: Mapped[str] = mapped_column(String(255), nullable=False)
    meal_service: Mapped[str] = mapped_column(String(64), nullable=False, default="Déjeuner")
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discard_on: Mapped[date] = mapped_column(Date, nullable=False)


class OilChangeAction(StrEnum):
    """Fryer oil maintenance action recorded on the tablet."""

    FILTER = "FILTER"
    OIL_CHANGE = "OIL_CHANGE"


class StorageLocation(StrEnum):
    """Where an opened product is stored after labelling."""

    COLD_POSITIVE = "COLD_POSITIVE"
    COLD_NEGATIVE = "COLD_NEGATIVE"
    AMBIENT = "AMBIENT"


class OilChangeRecord(TimestampMixin, Base):
    """Fryer oil filtration or full change with optional polar test."""

    __tablename__ = "oil_change_records"

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
    fryer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[OilChangeAction] = mapped_column(
        Enum(OilChangeAction, name="oil_change_action", native_enum=True),
        nullable=False,
    )
    polar_test_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_conforme: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OpenedProductLabel(TimestampMixin, Base):
    """Secondary use-by label after opening a packaged product."""

    __tablename__ = "opened_product_labels"

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
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    secondary_use_by: Mapped[date] = mapped_column(Date, nullable=False)
    storage_location: Mapped[StorageLocation] = mapped_column(
        Enum(StorageLocation, name="storage_location", native_enum=True),
        nullable=False,
    )


class DailyMenuItem(TimestampMixin, Base):
    """Dish of the day with EU allergen declaration for the tablet board."""

    __tablename__ = "daily_menu_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_service: Mapped[str] = mapped_column(String(64), nullable=False, default="Déjeuner")
    dish_name: Mapped[str] = mapped_column(String(255), nullable=False)
    protein_type: Mapped[MenuProteinType] = mapped_column(
        Enum(MenuProteinType, name="menu_protein_type", native_enum=True),
        nullable=False,
        default=MenuProteinType.WHOLE_MEAT,
    )
    allergens: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False)
