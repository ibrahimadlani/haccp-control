"""Pydantic schemas for the Production domain."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.production.models import BatchStatut, FoodType, StepType


class ProductionBatchCreate(BaseModel):
    nom_recette: str = Field(min_length=1, max_length=255)
    food_type: FoodType = FoodType.AUTRE
    date_production: date | None = None


class ProductionBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    etablissement_id: UUID
    nom_recette: str
    food_type: FoodType
    date_production: date
    statut: BatchStatut
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ProductionBatchListResponse(BaseModel):
    items: list[ProductionBatchResponse]


class ProductionStepCreate(BaseModel):
    step_type: StepType
    temperature_mesuree: Decimal = Field(max_digits=6, decimal_places=2)
    operator_id: UUID


class ProductionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    step_type: StepType
    temperature_mesuree: Decimal
    timestamp: datetime
    operator_id: UUID


class ProductionStepListResponse(BaseModel):
    items: list[ProductionStepResponse]


class ProductionBatchIngredientCreate(BaseModel):
    """Request body for linking a reception lot to a production batch.

    Attributes:
        reception_item_id (UUID): The reception item (lot) used in the batch.
        quantity_used (Decimal): Quantity consumed (up to 3 decimal places).
        unit (str): Unit of measurement, e.g. "kg", "L", "pce".
    """

    reception_item_id: UUID
    quantity_used: Decimal = Field(max_digits=10, decimal_places=3, gt=0)
    unit: str = Field(min_length=1, max_length=20)


class ProductionBatchIngredientResponse(BaseModel):
    """Traceability record linking a production batch to a reception lot.

    Attributes:
        id (UUID): Record primary key.
        batch_id (UUID): The production batch.
        reception_item_id (UUID): The source reception item (lot).
        operator_id (UUID): Operator who recorded the ingredient use.
        quantity_used (Decimal): Quantity consumed.
        unit (str): Unit of measurement.
        created_at (datetime): When the link was created.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    reception_item_id: UUID
    operator_id: UUID
    quantity_used: Decimal
    unit: str
    created_at: datetime


class ProductionBatchIngredientListResponse(BaseModel):
    items: list[ProductionBatchIngredientResponse]
