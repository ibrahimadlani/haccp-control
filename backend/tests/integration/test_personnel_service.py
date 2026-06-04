"""Integration tests for app/modules/personnel/service.py."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.modules.personnel.models import Utilisateur
from app.modules.personnel.schemas import (
    OperatorCreate,
    PinResetRequest,
)
from app.modules.personnel.service import (
    create_operator,
    ensure_admin_org_access,
    get_operators,
    list_roles,
    reset_pin,
    soft_delete_operator,
)
from tests.integration.conftest import (
    make_base_seed,
    make_establishment_ctx,
    make_role,
    make_user,
)


# ── Roles ─────────────────────────────────────────────────────────────────────


async def test_list_roles_returns_seeded_roles(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await list_roles(test_db, seed.ctx)
    role_names = {r.nom_role for r in result}
    assert "MANAGER" in role_names
    assert "OPERATEUR" in role_names


# ── Operators ─────────────────────────────────────────────────────────────────


async def test_create_operator_hashes_pin(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(nom="Dupont", prenom="Jean", pin_code="5678")
    result = await create_operator(payload, test_db, seed.ctx)

    assert result.id is not None
    # PIN should never be returned in plain text
    assert not hasattr(result, "pin_code") or result.pin_code is None

    # Verify hash is stored correctly
    from sqlalchemy import select
    user = (await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == result.id)
    )).scalar_one()
    assert user.code_pin is not None
    assert verify_password("5678", user.code_pin) is True


async def test_create_operator_wrong_pin_does_not_verify(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(nom="Durand", prenom="Marie", pin_code="1111")
    result = await create_operator(payload, test_db, seed.ctx)

    user = (await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == result.id)
    )).scalar_one()
    assert verify_password("9999", user.code_pin) is False


async def test_reset_pin_changes_hash(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(nom="Martin", prenom="Luc", pin_code="1234")
    op_result = await create_operator(payload, test_db, seed.ctx)

    user_before = (await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == op_result.id)
    )).scalar_one()
    old_hash = user_before.code_pin

    await reset_pin(op_result.id, PinResetRequest(pin_code="5678"), test_db, seed.ctx)

    user_after = (await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == op_result.id)
    )).scalar_one()
    assert user_after.code_pin != old_hash
    assert verify_password("5678", user_after.code_pin) is True


async def test_get_operators_returns_created(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(nom="Bernard", prenom="Paul", pin_code="4321")
    await create_operator(payload, test_db, seed.ctx)

    result = await get_operators(test_db, seed.ctx)
    names = {op.nom for op in result.operators}
    assert "Bernard" in names


async def test_soft_delete_operator_deactivates(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(nom="Petit", prenom="Marc", pin_code="0000")
    op = await create_operator(payload, test_db, seed.ctx)

    await soft_delete_operator(op.id, test_db, seed.ctx)

    user = (await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == op.id)
    )).scalar_one()
    assert user.deleted_at is not None


# ── Access guards ─────────────────────────────────────────────────────────────


async def test_ensure_admin_org_access_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    # Build context with operator as manager_user_id (operator has no manager role)
    non_manager_ctx = make_establishment_ctx(
        seed.org, seed.est, seed.operator, is_org_admin=False
    )
    with pytest.raises(HTTPException) as exc_info:
        await ensure_admin_org_access(test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


async def test_ensure_admin_org_access_manager_passes(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    # seed.manager has MANAGER role → should pass without exception
    await ensure_admin_org_access(test_db, seed.ctx)
