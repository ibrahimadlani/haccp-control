"""Pydantic schemas for the Production domain."""

from datetime import date, datetime
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


class ProductionBatchListResponse(BaseModel):
    items: list[ProductionBatchResponse]


class ProductionStepCreate(BaseModel):
    step_type: StepType
    temperature_mesuree: float
    operator_id: UUID


class ProductionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    step_type: StepType
    temperature_mesuree: float
    timestamp: datetime
    operator_id: UUID


class ProductionStepListResponse(BaseModel):
    items: list[ProductionStepResponse]
