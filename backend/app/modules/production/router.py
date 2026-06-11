"""FastAPI router for the Production domain."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentSite, DatabaseSession
from app.modules.production import service
from app.modules.production.schemas import (
    ProductionBatchCreate,
    ProductionBatchListResponse,
    ProductionBatchResponse,
    ProductionStepCreate,
    ProductionStepListResponse,
    ProductionStepResponse,
)

router = APIRouter(tags=["Production"])


@router.post("/production-batches", response_model=ProductionBatchResponse, status_code=201)
async def create_production_batch(
    payload: ProductionBatchCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> ProductionBatchResponse:
    return await service.create_batch(payload, db, establishment)


@router.get("/production-batches", response_model=ProductionBatchListResponse)
async def list_production_batches(
    db: DatabaseSession,
    establishment: CurrentSite,
) -> ProductionBatchListResponse:
    return await service.list_batches(db, establishment)


@router.post(
    "/production-batches/{batch_id}/steps",
    response_model=ProductionStepResponse,
    status_code=201,
)
async def create_production_step(
    batch_id: UUID,
    payload: ProductionStepCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> ProductionStepResponse:
    return await service.record_production_step(batch_id, payload, db, establishment)


@router.get(
    "/production-batches/{batch_id}/steps",
    response_model=ProductionStepListResponse,
)
async def list_production_steps(
    batch_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> ProductionStepListResponse:
    return await service.list_steps(batch_id, db, establishment)
