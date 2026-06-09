from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.production.models import (
    MenuProteinType,
    OilChangeAction,
    ProductionControlType,
    StorageLocation,
)

EU_ALLERGENS = frozenset(
    {
        "Gluten",
        "Crustacés",
        "Œufs",
        "Poisson",
        "Arachides",
        "Soja",
        "Lait",
        "Fruits à coque",
        "Céleri",
        "Moutarde",
        "Sésame",
        "Sulfites",
        "Lupin",
        "Mollusques",
    }
)


class ProductionTemperatureCreate(BaseModel):
    dish_name: str = Field(min_length=1, max_length=255)
    control_type: ProductionControlType
    measured_value: Decimal
    menu_item_id: UUID | None = None


class ProductionTemperatureResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    dish_name: str
    control_type: ProductionControlType
    measured_value: Decimal
    min_required_c: Decimal
    is_conforme: bool
    measured_at: datetime


class WitnessSampleCreate(BaseModel):
    dish_name: str = Field(min_length=1, max_length=255)
    meal_service: str = Field(default="Déjeuner", max_length=64)


class WitnessSampleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    dish_name: str
    meal_service: str
    stored_at: datetime
    discard_on: date


class OilChangeCreate(BaseModel):
    fryer_name: str = Field(min_length=1, max_length=255)
    action: OilChangeAction
    polar_test_percent: Decimal | None = None

    @field_validator("polar_test_percent")
    @classmethod
    def validate_polar(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        if value < 0 or value > 100:
            raise ValueError("Le témoin polaire doit être entre 0 et 100 %.")
        return value


class OilChangeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    fryer_name: str
    action: OilChangeAction
    polar_test_percent: Decimal | None
    is_conforme: bool
    recorded_at: datetime


class OpenedProductLabelCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    secondary_use_by: date
    storage_location: StorageLocation


class OpenedProductLabelResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    product_name: str
    opened_at: datetime
    secondary_use_by: date
    storage_location: StorageLocation


class EstablishmentDocumentResponse(BaseModel):
    document_type: str
    url: str | None = None


class DailyMenuItemCreate(BaseModel):
    service_date: date
    meal_service: str = Field(default="Déjeuner", max_length=64)
    dish_name: str = Field(min_length=1, max_length=255)
    protein_type: MenuProteinType = MenuProteinType.WHOLE_MEAT
    allergens: list[str] = Field(default_factory=list)

    @field_validator("allergens")
    @classmethod
    def validate_allergens(cls, values: list[str]) -> list[str]:
        unknown = [a for a in values if a not in EU_ALLERGENS]
        if unknown:
            raise ValueError(f"Allergènes non reconnus : {', '.join(unknown)}")
        return values


class DailyMenuItemUpdate(BaseModel):
    meal_service: str | None = Field(default=None, max_length=64)
    dish_name: str | None = Field(default=None, min_length=1, max_length=255)
    protein_type: MenuProteinType | None = None
    allergens: list[str] | None = None

    @field_validator("allergens")
    @classmethod
    def validate_allergens(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        unknown = [a for a in values if a not in EU_ALLERGENS]
        if unknown:
            raise ValueError(f"Allergènes non reconnus : {', '.join(unknown)}")
        return values


class DailyMenuItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    service_date: date
    meal_service: str
    dish_name: str
    protein_type: MenuProteinType
    allergens: list[str]
    min_core_temp_c: Decimal | None = None
