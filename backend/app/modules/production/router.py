from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.core.s3 import S3Service, get_s3_service
from app.modules.production import service
from app.modules.production.schemas import (
    DailyMenuItemCreate,
    DailyMenuItemResponse,
    DailyMenuItemUpdate,
    EstablishmentDocumentResponse,
    OilChangeCreate,
    OilChangeResponse,
    OpenedProductLabelCreate,
    OpenedProductLabelResponse,
    ProductionTemperatureCreate,
    ProductionTemperatureResponse,
    WitnessSampleCreate,
    WitnessSampleResponse,
)

router = APIRouter(
    tags=["Production cantine"],
    dependencies=[Depends(require_feature(Feature.HACCP_TEMPERATURE))],
)


@router.post(
    "/production-temperature-records",
    response_model=ProductionTemperatureResponse,
    status_code=201,
)
async def create_production_temperature(
    payload: ProductionTemperatureCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> ProductionTemperatureResponse:
    return await service.create_production_temperature(payload, db, establishment, operator)


@router.get("/witness-samples", response_model=list[WitnessSampleResponse])
async def list_witness_samples(
    db: DatabaseSession,
    establishment: CurrentSite,
) -> list[WitnessSampleResponse]:
    return await service.list_today_witness_samples(db, establishment)


@router.post("/witness-samples", response_model=WitnessSampleResponse, status_code=201)
async def create_witness_sample(
    payload: WitnessSampleCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> WitnessSampleResponse:
    return await service.create_witness_sample(payload, db, establishment, operator)


@router.get("/oil-change-records", response_model=list[OilChangeResponse])
async def list_oil_changes(
    db: DatabaseSession,
    establishment: CurrentSite,
) -> list[OilChangeResponse]:
    return await service.list_today_oil_changes(db, establishment)


@router.post("/oil-change-records", response_model=OilChangeResponse, status_code=201)
async def create_oil_change(
    payload: OilChangeCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> OilChangeResponse:
    return await service.create_oil_change(payload, db, establishment, operator)


@router.get("/opened-product-labels", response_model=list[OpenedProductLabelResponse])
async def list_opened_labels(
    db: DatabaseSession,
    establishment: CurrentSite,
) -> list[OpenedProductLabelResponse]:
    return await service.list_active_opened_labels(db, establishment)


@router.post("/opened-product-labels", response_model=OpenedProductLabelResponse, status_code=201)
async def create_opened_label(
    payload: OpenedProductLabelCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
) -> OpenedProductLabelResponse:
    return await service.create_opened_product_label(payload, db, establishment, operator)


@router.get("/daily-menu", response_model=list[DailyMenuItemResponse])
async def list_daily_menu(
    db: DatabaseSession,
    establishment: CurrentSite,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> list[DailyMenuItemResponse]:
    return await service.list_menu_items(db, establishment, from_date, to_date)


@router.post("/daily-menu/items", response_model=DailyMenuItemResponse, status_code=201)
async def create_daily_menu_item(
    payload: DailyMenuItemCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> DailyMenuItemResponse:
    return await service.create_menu_item(payload, db, establishment)


@router.patch("/daily-menu/items/{item_id}", response_model=DailyMenuItemResponse)
async def update_daily_menu_item(
    item_id: UUID,
    payload: DailyMenuItemUpdate,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> DailyMenuItemResponse:
    return await service.update_menu_item(item_id, payload, db, establishment)


@router.delete("/daily-menu/items/{item_id}", status_code=204)
async def delete_daily_menu_item(
    item_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> None:
    await service.delete_menu_item(item_id, db, establishment)


@router.post("/establishment-documents", response_model=EstablishmentDocumentResponse, status_code=201)
async def upload_establishment_document(
    document_type: Annotated[str, Form()],
    photo: Annotated[UploadFile, File()],
    establishment: CurrentSite,
    operator: CurrentOperator,
    s3: Annotated[S3Service, Depends(get_s3_service)],
) -> EstablishmentDocumentResponse:
    return await service.upload_establishment_document(
        document_type, photo, establishment, operator, s3
    )
