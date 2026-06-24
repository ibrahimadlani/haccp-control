"""Integration tests for production batch ingredient traceability."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.production.models import FoodType, ProductionStep, StepType
from app.modules.production.schemas import (
    ProductionBatchIngredientCreate,
    ProductionStepCreate,
)
from app.modules.production.service import (
    link_ingredient_to_batch,
    list_batch_ingredients,
    record_production_step,
)
from tests.integration.conftest import (
    make_base_seed,
    make_lot_ouverture,
    make_product,
    make_production_batch,
    make_production_batch_ingredient,
    make_reception_item,
    make_reception_session,
    make_supplier,
)


async def test_link_ingredient_creates_record(test_db: AsyncSession):
    """Linking a reception lot to a batch creates the traceability record."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    batch = await make_production_batch(test_db, seed.est, operator=seed.operator)

    result = await link_ingredient_to_batch(
        batch.id,
        ProductionBatchIngredientCreate(
            reception_item_id=item.id,
            quantity_used=Decimal("2.500"),
            unit="kg",
        ),
        test_db,
        seed.ctx,
        seed.operator.id,
    )

    assert result.id is not None
    assert result.batch_id == batch.id
    assert result.reception_item_id == item.id
    assert result.quantity_used == Decimal("2.500")
    assert result.unit == "kg"


async def test_link_ingredient_duplicate_raises_409(test_db: AsyncSession):
    """Linking the same lot to the same batch twice raises 409."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    batch = await make_production_batch(test_db, seed.est)
    await make_production_batch_ingredient(test_db, batch, item, seed.operator)

    with pytest.raises(HTTPException) as exc:
        await link_ingredient_to_batch(
            batch.id,
            ProductionBatchIngredientCreate(
                reception_item_id=item.id,
                quantity_used=Decimal("1.000"),
                unit="kg",
            ),
            test_db,
            seed.ctx,
            seed.operator.id,
        )

    assert exc.value.status_code == 409


async def test_link_ingredient_wrong_batch_establishment_raises_404(test_db: AsyncSession):
    """Linking to a batch from another establishment raises 404."""
    seed1 = await make_base_seed(test_db)
    seed2 = await make_base_seed(test_db)

    supplier = await make_supplier(test_db, seed1.est)
    product = await make_product(test_db, seed1.est, supplier)
    session = await make_reception_session(test_db, seed1.est, seed1.operator, supplier)
    item = await make_reception_item(test_db, session, product)
    batch = await make_production_batch(test_db, seed1.est)

    with pytest.raises(HTTPException) as exc:
        await link_ingredient_to_batch(
            batch.id,
            ProductionBatchIngredientCreate(
                reception_item_id=item.id,
                quantity_used=Decimal("1.000"),
                unit="kg",
            ),
            test_db,
            seed2.ctx,
            seed2.operator.id,
        )

    assert exc.value.status_code == 404


async def test_link_ingredient_wrong_item_establishment_raises_404(test_db: AsyncSession):
    """Linking a reception item from another establishment to a batch raises 404."""
    seed1 = await make_base_seed(test_db)
    seed2 = await make_base_seed(test_db)

    supplier1 = await make_supplier(test_db, seed1.est)
    product1 = await make_product(test_db, seed1.est, supplier1)
    session1 = await make_reception_session(test_db, seed1.est, seed1.operator, supplier1)
    item_from_seed1 = await make_reception_item(test_db, session1, product1)

    batch = await make_production_batch(test_db, seed2.est)

    with pytest.raises(HTTPException) as exc:
        await link_ingredient_to_batch(
            batch.id,
            ProductionBatchIngredientCreate(
                reception_item_id=item_from_seed1.id,
                quantity_used=Decimal("1.000"),
                unit="kg",
            ),
            test_db,
            seed2.ctx,
            seed2.operator.id,
        )

    assert exc.value.status_code == 404


async def test_list_batch_ingredients_returns_linked_items(test_db: AsyncSession):
    """list_batch_ingredients returns all ingredients linked to a batch."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item1 = await make_reception_item(test_db, session, product)
    item2 = await make_reception_item(test_db, session, product)
    batch = await make_production_batch(test_db, seed.est)
    await make_production_batch_ingredient(test_db, batch, item1, seed.operator)
    await make_production_batch_ingredient(test_db, batch, item2, seed.operator)

    result = await list_batch_ingredients(batch.id, test_db, seed.ctx)

    assert len(result.items) == 2
    reception_ids = {i.reception_item_id for i in result.items}
    assert item1.id in reception_ids
    assert item2.id in reception_ids


async def test_refreeze_refused_if_ingredient_was_frozen_without_cooking(test_db: AsyncSession):
    """REFROIDISSEMENT_DEBUT is refused when a frozen ingredient has no cooking step."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product, is_surgele=True)
    await make_lot_ouverture(test_db, seed.est, item, seed.operator)

    batch = await make_production_batch(test_db, seed.est, food_type=FoodType.VOLAILLE)
    await make_production_batch_ingredient(test_db, batch, item, seed.operator)

    with pytest.raises(HTTPException) as exc:
        await record_production_step(
            batch.id,
            ProductionStepCreate(
                step_type=StepType.REFROIDISSEMENT_DEBUT,
                temperature_mesuree=Decimal("65.0"),
                operator_id=seed.operator.id,
            ),
            test_db,
            seed.ctx,
        )

    assert exc.value.status_code == 409
    assert "surgelé" in exc.value.detail.lower() or "recongélation" in exc.value.detail.lower()


async def test_refreeze_allowed_if_cooking_step_exists_before_refroidissement(
    test_db: AsyncSession,
):
    """REFROIDISSEMENT_DEBUT is allowed when a frozen ingredient was cooked first."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product, is_surgele=True)
    await make_lot_ouverture(test_db, seed.est, item, seed.operator)

    batch = await make_production_batch(test_db, seed.est, food_type=FoodType.VOLAILLE)
    await make_production_batch_ingredient(test_db, batch, item, seed.operator)

    # First record a cooking step (74°C for volaille — compliant).
    cuisson_step = ProductionStep(
        batch_id=batch.id,
        step_type=StepType.CUISSON_A_COEUR,
        temperature_mesuree=Decimal("75.0"),
        timestamp=datetime.now(UTC),
        operator_id=seed.operator.id,
    )
    test_db.add(cuisson_step)
    await test_db.flush()

    # Now cooling should be allowed.
    result = await record_production_step(
        batch.id,
        ProductionStepCreate(
            step_type=StepType.REFROIDISSEMENT_DEBUT,
            temperature_mesuree=Decimal("65.0"),
            operator_id=seed.operator.id,
        ),
        test_db,
        seed.ctx,
    )

    assert result.step_type == StepType.REFROIDISSEMENT_DEBUT


async def test_refreeze_check_passes_for_non_frozen_ingredients(test_db: AsyncSession):
    """REFROIDISSEMENT_DEBUT is allowed when no ingredient was frozen."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product, is_surgele=False)

    batch = await make_production_batch(test_db, seed.est, food_type=FoodType.LEGUMES_FECULENTS)
    await make_production_batch_ingredient(test_db, batch, item, seed.operator)

    result = await record_production_step(
        batch.id,
        ProductionStepCreate(
            step_type=StepType.REFROIDISSEMENT_DEBUT,
            temperature_mesuree=Decimal("65.0"),
            operator_id=seed.operator.id,
        ),
        test_db,
        seed.ctx,
    )

    assert result.step_type == StepType.REFROIDISSEMENT_DEBUT


async def test_batch_without_ingredients_allows_cooling(test_db: AsyncSession):
    """REFROIDISSEMENT_DEBUT on a batch with no linked ingredients is allowed."""
    seed = await make_base_seed(test_db)
    batch = await make_production_batch(test_db, seed.est)

    result = await record_production_step(
        batch.id,
        ProductionStepCreate(
            step_type=StepType.REFROIDISSEMENT_DEBUT,
            temperature_mesuree=Decimal("65.0"),
            operator_id=seed.operator.id,
        ),
        test_db,
        seed.ctx,
    )

    assert result.step_type == StepType.REFROIDISSEMENT_DEBUT


async def test_link_ingredient_unknown_batch_raises_404(test_db: AsyncSession):
    """Linking to a non-existent batch ID raises 404."""
    seed = await make_base_seed(test_db)
    supplier = await make_supplier(test_db, seed.est)
    product = await make_product(test_db, seed.est, supplier)
    session = await make_reception_session(test_db, seed.est, seed.operator, supplier)
    item = await make_reception_item(test_db, session, product)

    with pytest.raises(HTTPException) as exc:
        await link_ingredient_to_batch(
            uuid.uuid4(),
            ProductionBatchIngredientCreate(
                reception_item_id=item.id,
                quantity_used=Decimal("1.000"),
                unit="kg",
            ),
            test_db,
            seed.ctx,
            seed.operator.id,
        )

    assert exc.value.status_code == 404
