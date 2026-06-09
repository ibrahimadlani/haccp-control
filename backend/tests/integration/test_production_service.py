"""Integration tests for app/modules/production/service.py."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.modules.production.models import DailyMenuItem, MenuProteinType, OilChangeAction, StorageLocation
from app.modules.production.schemas import (
    OilChangeCreate,
    OpenedProductLabelCreate,
    ProductionTemperatureCreate,
    WitnessSampleCreate,
)
from app.modules.production.service import (
    create_oil_change,
    create_opened_product_label,
    create_production_temperature,
    create_witness_sample,
    list_menu_items,
)
from app.core.time_utils import now_for_site
from tests.integration.conftest import make_base_seed


async def test_create_production_temperature_conforme(test_db):
    seed = await make_base_seed(test_db)
    result = await create_production_temperature(
        ProductionTemperatureCreate(
            dish_name="Purée",
            control_type="COOKING_CORE",
            measured_value=Decimal("72"),
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert result.is_conforme is True


async def test_create_oil_change_filter_non_conforme(test_db):
    seed = await make_base_seed(test_db)
    result = await create_oil_change(
        OilChangeCreate(
            fryer_name="Friteuse 1",
            action=OilChangeAction.FILTER,
            polar_test_percent=Decimal("28"),
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert result.is_conforme is False


async def test_create_oil_change_requires_polar_for_filter(test_db):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await create_oil_change(
            OilChangeCreate(fryer_name="Friteuse 1", action=OilChangeAction.FILTER),
            test_db,
            seed.ctx,
            seed.operator,
        )
    assert exc_info.value.status_code == 422


async def test_create_opened_product_label(test_db):
    seed = await make_base_seed(test_db)
    result = await create_opened_product_label(
        OpenedProductLabelCreate(
            product_name="Mayonnaise",
            secondary_use_by=date.today() + timedelta(days=2),
            storage_location=StorageLocation.COLD_POSITIVE,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert result.product_name == "Mayonnaise"


async def test_create_witness_sample(test_db):
    seed = await make_base_seed(test_db)
    result = await create_witness_sample(
        WitnessSampleCreate(dish_name="Gratin", meal_service="Déjeuner"),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert result.discard_on >= date.today()


async def test_list_menu_items_empty_without_seed(test_db):
    seed = await make_base_seed(test_db)
    items = await list_menu_items(test_db, seed.ctx)
    assert items == []


async def test_production_temperature_poultry_requires_75c(test_db):
    seed = await make_base_seed(test_db)
    today = now_for_site(seed.ctx.timezone).date()
    menu_item = DailyMenuItem(
        establishment_id=seed.ctx.etablissement_id,
        service_date=today,
        meal_service="Déjeuner",
        dish_name="Poulet rôti",
        protein_type=MenuProteinType.POULTRY,
        allergens=[],
    )
    test_db.add(menu_item)
    await test_db.commit()
    await test_db.refresh(menu_item)

    low = await create_production_temperature(
        ProductionTemperatureCreate(
            dish_name="Poulet rôti",
            control_type="COOKING_CORE",
            measured_value=Decimal("70"),
            menu_item_id=menu_item.id,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert low.is_conforme is False
    assert low.min_required_c == Decimal("75.00")

    ok = await create_production_temperature(
        ProductionTemperatureCreate(
            dish_name="Poulet rôti",
            control_type="COOKING_CORE",
            measured_value=Decimal("76"),
            menu_item_id=menu_item.id,
        ),
        test_db,
        seed.ctx,
        seed.operator,
    )
    assert ok.is_conforme is True
