"""Integration tests for app/modules/equipments/service.py."""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipments.models import Equipement, TypeEquipement
from app.modules.equipments.schemas import (
    EquipmentCreateRequest,
    EquipmentUpdateRequest,
)
from app.modules.equipments.service import (
    create_equipment,
    delete_equipment,
    list_equipment,
    update_equipment,
)
from tests.integration.conftest import (
    make_base_seed,
    make_equipment,
    make_establishment_ctx,
)

# ── Create ────────────────────────────────────────────────────────────────────


async def test_create_equipment_happy_path(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = EquipmentCreateRequest(
        name="Chambre froide entrée",
        equipment_type=TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
        min_target_temperature=Decimal("0.00"),
        max_target_temperature=Decimal("4.00"),
        establishment_id=seed.est.id,
    )
    result = await create_equipment(payload, test_db, seed.ctx)

    assert result.id is not None
    assert result.name == "Chambre froide entrée"
    assert result.equipment_type == TypeEquipement.CHAMBRE_FROIDE_POSITIVE
    assert result.min_target_temperature == Decimal("0.00")
    assert result.max_target_temperature == Decimal("4.00")
    assert result.is_active is True


async def test_create_equipment_negative_temperature(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = EquipmentCreateRequest(
        name="Surgélateur",
        equipment_type=TypeEquipement.CHAMBRE_FROIDE_NEGATIVE,
        min_target_temperature=Decimal("-25.00"),
        max_target_temperature=Decimal("-18.00"),
        establishment_id=seed.est.id,
    )
    result = await create_equipment(payload, test_db, seed.ctx)
    assert result.min_target_temperature == Decimal("-25.00")


async def test_create_equipment_wrong_establishment_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = EquipmentCreateRequest(
        name="Frigo introuvable",
        equipment_type=TypeEquipement.REFRIGERATEUR,
        min_target_temperature=Decimal("0.00"),
        max_target_temperature=Decimal("4.00"),
        establishment_id=uuid.uuid4(),  # non-existent establishment
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_equipment(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_create_equipment_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
    payload = EquipmentCreateRequest(
        name="Frigo",
        equipment_type=TypeEquipement.REFRIGERATEUR,
        min_target_temperature=Decimal("0.00"),
        max_target_temperature=Decimal("4.00"),
        establishment_id=seed.est.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_equipment(payload, test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


# ── List ──────────────────────────────────────────────────────────────────────


async def test_list_equipment_returns_created(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await make_equipment(test_db, seed.est, nom="Frigo A")
    await make_equipment(test_db, seed.est, nom="Frigo B")

    result = await list_equipment(test_db, seed.ctx)
    names = {e.name for e in result.items}
    assert "Frigo A" in names
    assert "Frigo B" in names


async def test_list_equipment_excludes_soft_deleted(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est, nom="Supprimé")
    await delete_equipment(equip.id, test_db, seed.ctx)

    result = await list_equipment(test_db, seed.ctx)
    assert "Supprimé" not in {e.name for e in result.items}


async def test_list_equipment_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        await list_equipment(test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


# ── Update ────────────────────────────────────────────────────────────────────


async def test_update_equipment_name(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est, nom="Ancien nom")

    result = await update_equipment(
        equip.id, EquipmentUpdateRequest(name="Nouveau nom"), test_db, seed.ctx
    )
    assert result.name == "Nouveau nom"


async def test_update_equipment_temperature_bounds(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(
        test_db, seed.est, min_temp=Decimal("0.00"), max_temp=Decimal("4.00")
    )

    result = await update_equipment(
        equip.id,
        EquipmentUpdateRequest(max_target_temperature=Decimal("6.00")),
        test_db,
        seed.ctx,
    )
    assert result.max_target_temperature == Decimal("6.00")


async def test_update_equipment_invalid_temp_range_raises_422(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(
        test_db, seed.est, min_temp=Decimal("0.00"), max_temp=Decimal("4.00")
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_equipment(
            equip.id,
            EquipmentUpdateRequest(min_target_temperature=Decimal("5.00")),
            test_db,
            seed.ctx,
        )
    assert exc_info.value.status_code == 422


async def test_update_equipment_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await update_equipment(uuid.uuid4(), EquipmentUpdateRequest(name="X"), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_delete_equipment_soft_delete(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)

    await delete_equipment(equip.id, test_db, seed.ctx)

    row = (await test_db.execute(select(Equipement).where(Equipement.id == equip.id))).scalar_one()
    assert row.deleted_at is not None


async def test_delete_equipment_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await delete_equipment(uuid.uuid4(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_delete_already_soft_deleted_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    equip = await make_equipment(test_db, seed.est)
    await delete_equipment(equip.id, test_db, seed.ctx)

    with pytest.raises(HTTPException) as exc_info:
        await delete_equipment(equip.id, test_db, seed.ctx)
    assert exc_info.value.status_code == 404
