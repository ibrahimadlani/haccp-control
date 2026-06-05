from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.time_utils import now_for_site
from app.modules.personnel.models import Utilisateur

from app.modules.production.models import (
    MAX_POLAR_TEST_PERCENT,
    MIN_HOT_TEMPERATURE_C,
    DailyMenuItem,
    OilChangeAction,
    OilChangeRecord,
    OpenedProductLabel,
    ProductionTemperatureRecord,
    WitnessSample,
)
from app.modules.production.schemas import (
    DailyMenuItemResponse,
    OilChangeCreate,
    OilChangeResponse,
    OpenedProductLabelCreate,
    OpenedProductLabelResponse,
    ProductionTemperatureCreate,
    ProductionTemperatureResponse,
    WitnessSampleCreate,
    WitnessSampleResponse,
)


async def create_production_temperature(
    payload: ProductionTemperatureCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator: Utilisateur,
) -> ProductionTemperatureResponse:
    measured = Decimal(str(payload.measured_value))
    is_conforme = measured >= MIN_HOT_TEMPERATURE_C
    record = ProductionTemperatureRecord(
        establishment_id=establishment.etablissement_id,
        operator_id=operator.id,
        dish_name=payload.dish_name.strip(),
        control_type=payload.control_type,
        measured_value=measured,
        min_required_c=MIN_HOT_TEMPERATURE_C,
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


async def list_today_menu(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[DailyMenuItemResponse]:
    today = now_for_site(establishment.timezone).date()
    result = await db.execute(
        select(DailyMenuItem)
        .where(
            DailyMenuItem.establishment_id == establishment.etablissement_id,
            DailyMenuItem.service_date == today,
        )
        .order_by(DailyMenuItem.meal_service.asc(), DailyMenuItem.dish_name.asc())
    )
    return [DailyMenuItemResponse.model_validate(row) for row in result.scalars().all()]
