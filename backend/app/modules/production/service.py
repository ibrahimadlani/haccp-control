"""Business logic for the Production domain."""

from datetime import datetime
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
    ProductionStep,
    StepType,
)
from app.modules.production.schemas import (
    ProductionBatchCreate,
    ProductionBatchListResponse,
    ProductionBatchResponse,
    ProductionStepCreate,
    ProductionStepListResponse,
    ProductionStepResponse,
)

COOKING_TARGETS: dict[FoodType, float] = {
    FoodType.VOLAILLE: 74.0,
    FoodType.VIANDE_HACHEE: 65.0,
    FoodType.POISSON: 65.0,
    FoodType.VIANDE_PIECE: 55.0,
    FoodType.LEGUMES_FECULENTS: 63.0,
    FoodType.AUTRE: 63.0,
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
MAX_RAPID_COOLING_TEMP_C = 10.0


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
    elif step.step_type == StepType.REFROIDISSEMENT_FIN:
        await _check_refroidissement_rule(step, db, establishment)

    await db.commit()
    await db.refresh(step)
    return ProductionStepResponse.model_validate(step)


async def create_batch(
    payload: ProductionBatchCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> ProductionBatchResponse:
    site_now = now_for_site(establishment.timezone)
    batch = ProductionBatch(
        etablissement_id=establishment.etablissement_id,
        nom_recette=payload.nom_recette,
        food_type=payload.food_type,
        date_production=payload.date_production or site_now.date(),
        statut=BatchStatut.EN_COURS,
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
