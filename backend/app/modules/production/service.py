"""Business logic for the Production domain."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentEstablishment
from app.core.time_utils import now_for_site
from app.modules.production.models import (
    BatchStatut,
    FoodType,
    ProductionBatch,
    ProductionBatchIngredient,
    ProductionStep,
    StepType,
)
from app.modules.production.schemas import (
    ProductionBatchCreate,
    ProductionBatchIngredientCreate,
    ProductionBatchIngredientListResponse,
    ProductionBatchIngredientResponse,
    ProductionBatchListResponse,
    ProductionBatchResponse,
    ProductionStepCreate,
    ProductionStepListResponse,
    ProductionStepResponse,
)
from app.modules.receptions.models import LotOuverture, ReceptionItem

# Use Decimal throughout so threshold comparisons are exact (IEEE 754 floats
# can represent 74.0 as 73.9999…, silently triggering a false non-conformity).
COOKING_TARGETS: dict[FoodType, Decimal] = {
    FoodType.VOLAILLE: Decimal("74.0"),
    FoodType.VIANDE_HACHEE: Decimal("65.0"),
    FoodType.POISSON: Decimal("65.0"),
    FoodType.VIANDE_PIECE: Decimal("55.0"),
    FoodType.LEGUMES_FECULENTS: Decimal("63.0"),
    FoodType.AUTRE: Decimal("63.0"),
}

FOOD_TYPE_LABELS: dict[FoodType, str] = {
    FoodType.VOLAILLE: "volaille",
    FoodType.VIANDE_HACHEE: "viande hachée",
    FoodType.VIANDE_PIECE: "viande en pièce",
    FoodType.LEGUMES_FECULENTS: "légumes / féculents",
    FoodType.POISSON: "poisson",
    FoodType.AUTRE: "autre",
}

MAX_RAPID_COOLING_MINUTES = 120
MAX_RAPID_COOLING_TEMP_C = Decimal("10.0")


async def _get_batch_in_scope(
    batch_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionBatch:
    result = await db.execute(
        select(ProductionBatch).where(
            ProductionBatch.id == batch_id,
            ProductionBatch.etablissement_id == establishment.etablissement_id,
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch introuvable.")
    return batch


async def _get_latest_step(
    batch_id: UUID,
    step_type: StepType,
    db: AsyncSession,
) -> ProductionStep | None:
    result = await db.execute(
        select(ProductionStep)
        .where(
            ProductionStep.batch_id == batch_id,
            ProductionStep.step_type == step_type,
        )
        .order_by(ProductionStep.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _check_cuisson_rule(
    batch: ProductionBatch,
    step: ProductionStep,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    target = COOKING_TARGETS[batch.food_type]
    if step.temperature_mesuree >= target:
        return

    label = FOOD_TYPE_LABELS[batch.food_type]
    reason = (
        f"Cuisson {label} insuffisante : {step.temperature_mesuree}°C mesuré, attendu {target:g}°C"
    )
    await _open_temperature_nc(db, establishment, step, reason)


async def _open_temperature_nc(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    step: ProductionStep,
    reason: str,
) -> None:
    from app.modules.nonconformities import service as nc_service

    await nc_service.open_manual_temperature_nonconformity(
        db,
        establishment_id=establishment.etablissement_id,
        opened_by_id=step.operator_id,
        opened_at=step.timestamp,
        reason=reason,
    )


async def _check_refroidissement_rule(
    step: ProductionStep,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    debut = await _get_latest_step(step.batch_id, StepType.REFROIDISSEMENT_DEBUT, db)
    if debut is None:
        await _open_temperature_nc(
            db, establishment, step, "Refroidissement : aucune étape de début enregistrée"
        )
        return

    delta_minutes = (step.timestamp - debut.timestamp).total_seconds() / 60
    issues: list[str] = []
    if delta_minutes > MAX_RAPID_COOLING_MINUTES:
        issues.append(f"temps écoulé {int(delta_minutes)} min")
    if step.temperature_mesuree > MAX_RAPID_COOLING_TEMP_C:
        issues.append(f"température finale {step.temperature_mesuree}°C")
    if not issues:
        return

    await _open_temperature_nc(
        db, establishment, step, f"Échec du refroidissement : {', '.join(issues)}"
    )


async def _check_no_refreeze_rule(
    batch_id: UUID,
    db: AsyncSession,
) -> None:
    """Refuse a cooling step if any linked ingredient was frozen but never cooked.

    An ingredient that arrived frozen (``LotOuverture.was_frozen``) and was
    opened (``StatutOuverture.OUVERT`` or any closed state) must have undergone
    a ``CUISSON_A_COEUR`` step in the same batch before it can be cooled again.
    Re-freezing without cooking is prohibited by French food-safety regulations.

    Args:
        batch_id (UUID): The batch about to record a cooling step.
        db (AsyncSession): The async database session.

    Raises:
        HTTPException: 409 Conflict if a frozen ingredient has not been cooked.
    """
    # Check if any linked ingredient was frozen at opening time.
    frozen_ingredient_result = await db.execute(
        select(ProductionBatchIngredient)
        .join(ReceptionItem, ProductionBatchIngredient.reception_item_id == ReceptionItem.id)
        .join(LotOuverture, LotOuverture.reception_item_id == ReceptionItem.id)
        .where(
            ProductionBatchIngredient.batch_id == batch_id,
            LotOuverture.was_frozen.is_(True),
        )
        .limit(1)
    )
    has_frozen_ingredient = frozen_ingredient_result.scalar_one_or_none() is not None

    if not has_frozen_ingredient:
        return

    # A frozen ingredient is present — check that at least one cooking step exists.
    cuisson_result = await db.execute(
        select(ProductionStep).where(
            ProductionStep.batch_id == batch_id,
            ProductionStep.step_type == StepType.CUISSON_A_COEUR,
        )
    )
    if cuisson_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Recongélation interdite : un ingrédient de ce batch était surgelé "
                "et n'a pas encore subi d'étape de cuisson à cœur."
            ),
        )


async def record_production_step(
    batch_id: UUID,
    payload: ProductionStepCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionStepResponse:
    batch = await _get_batch_in_scope(batch_id, db, establishment)
    timestamp = now_for_site(establishment.timezone)
    step = ProductionStep(
        batch_id=batch.id,
        step_type=payload.step_type,
        temperature_mesuree=payload.temperature_mesuree,
        timestamp=timestamp,
        operator_id=payload.operator_id,
    )
    db.add(step)
    await db.flush()

    if step.step_type == StepType.CUISSON_A_COEUR:
        await _check_cuisson_rule(batch, step, db, establishment)
    elif step.step_type == StepType.REFROIDISSEMENT_DEBUT:
        # Enforce no-refreeze rule before starting the cooling phase.
        await _check_no_refreeze_rule(batch_id, db)
    elif step.step_type == StepType.REFROIDISSEMENT_FIN:
        await _check_refroidissement_rule(step, db, establishment)

    await db.commit()
    await db.refresh(step)
    return ProductionStepResponse.model_validate(step)


async def create_batch(
    payload: ProductionBatchCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator_id: UUID | None = None,
) -> ProductionBatchResponse:
    site_now = now_for_site(establishment.timezone)
    batch = ProductionBatch(
        etablissement_id=establishment.etablissement_id,
        nom_recette=payload.nom_recette,
        food_type=payload.food_type,
        date_production=payload.date_production or site_now.date(),
        statut=BatchStatut.EN_COURS,
        created_by_id=operator_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return ProductionBatchResponse.model_validate(batch)


async def list_batches(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionBatchListResponse:
    result = await db.execute(
        select(ProductionBatch)
        .where(ProductionBatch.etablissement_id == establishment.etablissement_id)
        .order_by(ProductionBatch.date_production.desc(), ProductionBatch.nom_recette)
    )
    batches = result.scalars().all()
    return ProductionBatchListResponse(
        items=[ProductionBatchResponse.model_validate(batch) for batch in batches]
    )


async def list_steps(
    batch_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionStepListResponse:
    await _get_batch_in_scope(batch_id, db, establishment)
    result = await db.execute(
        select(ProductionStep)
        .where(ProductionStep.batch_id == batch_id)
        .order_by(ProductionStep.timestamp)
    )
    steps = result.scalars().all()
    return ProductionStepListResponse(
        items=[ProductionStepResponse.model_validate(step) for step in steps]
    )


async def link_ingredient_to_batch(
    batch_id: UUID,
    payload: ProductionBatchIngredientCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator_id: UUID,
) -> ProductionBatchIngredientResponse:
    """Link a reception lot to a production batch for downstream traceability.

    Validates that:
    - The batch exists and belongs to this establishment.
    - The reception item exists and belongs to this establishment.
    - The combination (batch, reception_item) is not already linked.

    Args:
        batch_id (UUID): The production batch.
        payload (ProductionBatchIngredientCreate): Reception item ID + quantity.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        operator_id (UUID): The operator recording the ingredient use.

    Returns:
        ProductionBatchIngredientResponse: The created traceability record.

    Raises:
        HTTPException: 404 if batch or reception item not found.
        HTTPException: 409 if the link already exists.
    """
    from sqlalchemy.exc import IntegrityError

    await _get_batch_in_scope(batch_id, db, establishment)

    # Verify the reception item belongs to this establishment via its session.
    from app.modules.receptions.models import ReceptionSession

    item_result = await db.execute(
        select(ReceptionItem)
        .join(ReceptionSession, ReceptionItem.session_id == ReceptionSession.id)
        .where(
            ReceptionItem.id == payload.reception_item_id,
            ReceptionSession.establishment_id == establishment.etablissement_id,
        )
    )
    if item_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lot de réception introuvable pour cet établissement.",
        )

    ingredient = ProductionBatchIngredient(
        batch_id=batch_id,
        reception_item_id=payload.reception_item_id,
        operator_id=operator_id,
        quantity_used=payload.quantity_used,
        unit=payload.unit,
    )
    db.add(ingredient)
    try:
        await db.commit()
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce lot est déjà lié à ce batch de production.",
        ) from err
    await db.refresh(ingredient)
    return ProductionBatchIngredientResponse.model_validate(ingredient)


async def list_batch_ingredients(
    batch_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionBatchIngredientListResponse:
    """Return all ingredient links for a production batch.

    Args:
        batch_id (UUID): The production batch.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        ProductionBatchIngredientListResponse: All traceability links for the batch.
    """
    await _get_batch_in_scope(batch_id, db, establishment)
    result = await db.execute(
        select(ProductionBatchIngredient)
        .where(ProductionBatchIngredient.batch_id == batch_id)
        .order_by(ProductionBatchIngredient.created_at)
    )
    items = result.scalars().all()
    return ProductionBatchIngredientListResponse(
        items=[ProductionBatchIngredientResponse.model_validate(i) for i in items]
    )
