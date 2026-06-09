from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select

from app.core.s3 import S3Service
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.time_utils import now_for_site
from app.modules.personnel.models import Utilisateur

from app.modules.production.models import (
    CORE_TEMP_BY_PROTEIN,
    MAX_POLAR_TEST_PERCENT,
    MIN_HOT_TEMPERATURE_C,
    DailyMenuItem,
    MenuProteinType,
    OilChangeAction,
    OilChangeRecord,
    OpenedProductLabel,
    ProductionControlType,
    ProductionTemperatureRecord,
    WitnessSample,
)
from app.modules.production.schemas import (
    DailyMenuItemCreate,
    DailyMenuItemResponse,
    DailyMenuItemUpdate,
    OilChangeCreate,
    OilChangeResponse,
    OpenedProductLabelCreate,
    EstablishmentDocumentResponse,
    OpenedProductLabelResponse,
    ProductionTemperatureCreate,
    ProductionTemperatureResponse,
    WitnessSampleCreate,
    WitnessSampleResponse,
)


def _menu_item_response(item: DailyMenuItem) -> DailyMenuItemResponse:
    data = DailyMenuItemResponse.model_validate(item)
    return data.model_copy(
        update={"min_core_temp_c": CORE_TEMP_BY_PROTEIN.get(item.protein_type, MIN_HOT_TEMPERATURE_C)}
    )


async def _resolve_min_required(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    dish_name: str,
    control_type: ProductionControlType,
    menu_item_id: UUID | None,
) -> Decimal:
    if control_type == ProductionControlType.HOT_HOLDING:
        return MIN_HOT_TEMPERATURE_C

    item: DailyMenuItem | None = None
    if menu_item_id is not None:
        result = await db.execute(
            select(DailyMenuItem).where(
                DailyMenuItem.id == menu_item_id,
                DailyMenuItem.establishment_id == establishment.etablissement_id,
            )
        )
        item = result.scalar_one_or_none()
    if item is None:
        today = now_for_site(establishment.timezone).date()
        result = await db.execute(
            select(DailyMenuItem).where(
                DailyMenuItem.establishment_id == establishment.etablissement_id,
                DailyMenuItem.service_date == today,
                DailyMenuItem.dish_name == dish_name.strip(),
            )
        )
        item = result.scalar_one_or_none()

    if item is not None:
        return CORE_TEMP_BY_PROTEIN.get(item.protein_type, MIN_HOT_TEMPERATURE_C)
    return MIN_HOT_TEMPERATURE_C


async def create_production_temperature(
    payload: ProductionTemperatureCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> ProductionTemperatureResponse:
    measured = Decimal(str(payload.measured_value))
    min_required = await _resolve_min_required(
        db,
        establishment,
        payload.dish_name,
        payload.control_type,
        payload.menu_item_id,
    )
    is_conforme = measured >= min_required
    record = ProductionTemperatureRecord(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        dish_name=payload.dish_name.strip(),
        control_type=payload.control_type,
        measured_value=measured,
        min_required_c=min_required,
        is_conforme=is_conforme,
        measured_at=now_for_site(establishment.timezone),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ProductionTemperatureResponse.model_validate(record)


async def list_today_witness_samples(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[WitnessSampleResponse]:
    today = now_for_site(establishment.timezone).date()
    result = await db.execute(
        select(WitnessSample)
        .where(
            WitnessSample.establishment_id == establishment.etablissement_id,
            WitnessSample.discard_on >= today,
        )
        .order_by(WitnessSample.stored_at.desc())
    )
    return [WitnessSampleResponse.model_validate(row) for row in result.scalars().all()]


async def create_witness_sample(
    payload: WitnessSampleCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> WitnessSampleResponse:
    stored_at = now_for_site(establishment.timezone)
    sample = WitnessSample(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        dish_name=payload.dish_name.strip(),
        meal_service=payload.meal_service.strip() or "Déjeuner",
        stored_at=stored_at,
        discard_on=(stored_at + timedelta(days=5)).date(),
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return WitnessSampleResponse.model_validate(sample)


async def list_today_oil_changes(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[OilChangeResponse]:
    now = now_for_site(establishment.timezone)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(OilChangeRecord)
        .where(
            OilChangeRecord.establishment_id == establishment.etablissement_id,
            OilChangeRecord.recorded_at >= start_of_day,
        )
        .order_by(OilChangeRecord.recorded_at.desc())
    )
    return [OilChangeResponse.model_validate(row) for row in result.scalars().all()]


async def create_oil_change(
    payload: OilChangeCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> OilChangeResponse:
    if payload.action == OilChangeAction.FILTER and payload.polar_test_percent is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le témoin polaire est obligatoire après filtration.",
        )
    if payload.action == OilChangeAction.OIL_CHANGE and payload.polar_test_percent is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pas de témoin polaire lors d'un changement complet d'huile.",
        )

    polar: Decimal | None = None
    is_conforme = True
    if payload.action == OilChangeAction.FILTER:
        polar = Decimal(str(payload.polar_test_percent))
        is_conforme = polar <= MAX_POLAR_TEST_PERCENT

    record = OilChangeRecord(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        fryer_name=payload.fryer_name.strip(),
        action=payload.action,
        polar_test_percent=polar,
        is_conforme=is_conforme,
        recorded_at=now_for_site(establishment.timezone),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return OilChangeResponse.model_validate(record)


async def list_active_opened_labels(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[OpenedProductLabelResponse]:
    today = now_for_site(establishment.timezone).date()
    result = await db.execute(
        select(OpenedProductLabel)
        .where(
            OpenedProductLabel.establishment_id == establishment.etablissement_id,
            OpenedProductLabel.secondary_use_by >= today,
        )
        .order_by(OpenedProductLabel.secondary_use_by.asc())
    )
    return [OpenedProductLabelResponse.model_validate(row) for row in result.scalars().all()]


async def create_opened_product_label(
    payload: OpenedProductLabelCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> OpenedProductLabelResponse:
    today = now_for_site(establishment.timezone).date()
    if payload.secondary_use_by < today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La DLC secondaire ne peut pas être dans le passé.",
        )

    label = OpenedProductLabel(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        product_name=payload.product_name.strip(),
        opened_at=now_for_site(establishment.timezone),
        secondary_use_by=payload.secondary_use_by,
        storage_location=payload.storage_location,
    )
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return OpenedProductLabelResponse.model_validate(label)


async def list_menu_items(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[DailyMenuItemResponse]:
    today = now_for_site(establishment.timezone).date()
    start = from_date or today
    end = to_date or today
    result = await db.execute(
        select(DailyMenuItem)
        .where(
            DailyMenuItem.establishment_id == establishment.etablissement_id,
            DailyMenuItem.service_date >= start,
            DailyMenuItem.service_date <= end,
        )
        .order_by(
            DailyMenuItem.service_date.asc(),
            DailyMenuItem.meal_service.asc(),
            DailyMenuItem.dish_name.asc(),
        )
    )
    return [_menu_item_response(row) for row in result.scalars().all()]


async def create_menu_item(
    payload: DailyMenuItemCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> DailyMenuItemResponse:
    item = DailyMenuItem(
        establishment_id=establishment.etablissement_id,
        service_date=payload.service_date,
        meal_service=payload.meal_service.strip() or "Déjeuner",
        dish_name=payload.dish_name.strip(),
        protein_type=payload.protein_type,
        allergens=payload.allergens,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _menu_item_response(item)


async def update_menu_item(
    item_id: UUID,
    payload: DailyMenuItemUpdate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> DailyMenuItemResponse:
    result = await db.execute(
        select(DailyMenuItem).where(
            DailyMenuItem.id == item_id,
            DailyMenuItem.establishment_id == establishment.etablissement_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plat introuvable.")

    if payload.meal_service is not None:
        item.meal_service = payload.meal_service.strip() or item.meal_service
    if payload.dish_name is not None:
        item.dish_name = payload.dish_name.strip()
    if payload.protein_type is not None:
        item.protein_type = payload.protein_type
    if payload.allergens is not None:
        item.allergens = payload.allergens

    await db.commit()
    await db.refresh(item)
    return _menu_item_response(item)


async def delete_menu_item(
    item_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    result = await db.execute(
        select(DailyMenuItem).where(
            DailyMenuItem.id == item_id,
            DailyMenuItem.establishment_id == establishment.etablissement_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plat introuvable.")
    await db.delete(item)
    await db.commit()


async def upload_establishment_document(
    document_type: str,
    photo: UploadFile,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
    s3: S3Service,
) -> EstablishmentDocumentResponse:
    safe_type = document_type.strip().upper().replace(" ", "_")[:64] or "DOCUMENT"
    prefix = f"establishment-docs/{establishment.etablissement_id}/{safe_type}"
    key = await s3.upload_image(photo, prefix=prefix)
    _ = operator  # signature traceability — operator authenticated at router layer
    return EstablishmentDocumentResponse(
        document_type=safe_type,
        url=s3.object_url(key),
    )
