"""Integration tests for app/modules/personnel/service.py."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.modules.personnel.models import Operator
from app.modules.personnel.schemas import (
    OperatorCreate,
    PinResetRequest,
    UserCreateRequest,
)
from app.modules.personnel.service import (
    create_operator,
    create_user,
    ensure_admin_org_access,
    get_operators,
    list_roles,
    list_users,
    reset_pin,
    soft_delete_operator,
    update_operator,
)
from tests.integration.conftest import (
    make_base_seed,
    make_establishment_ctx,
)

# ── Roles ─────────────────────────────────────────────────────────────────────


async def test_list_roles_returns_seeded_roles(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await list_roles(test_db, seed.ctx)
    role_names = {r.role_name for r in result}
    assert "MANAGER" in role_names
    assert "OPERATEUR" in role_names


# ── Operators ─────────────────────────────────────────────────────────────────


async def test_create_operator_hashes_pin(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Jean", last_name="Dupont", pin_code="5678")
    result = await create_operator(payload, test_db, seed.ctx)

    assert result.id is not None
    operator = (
        await test_db.execute(select(Operator).where(Operator.id == result.id))
    ).scalar_one()
    assert verify_password("5678", operator.pin_hash) is True


async def test_create_operator_wrong_pin_does_not_verify(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Marie", last_name="Durand", pin_code="1111")
    result = await create_operator(payload, test_db, seed.ctx)

    operator = (
        await test_db.execute(select(Operator).where(Operator.id == result.id))
    ).scalar_one()
    assert verify_password("9999", operator.pin_hash) is False


async def test_reset_pin_changes_hash(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Luc", last_name="Martin", pin_code="1234")
    op_result = await create_operator(payload, test_db, seed.ctx)

    operator_before = (
        await test_db.execute(select(Operator).where(Operator.id == op_result.id))
    ).scalar_one()
    old_hash = operator_before.pin_hash

    await reset_pin(op_result.id, PinResetRequest(pin_code="5678"), test_db, seed.ctx)

    operator_after = (
        await test_db.execute(select(Operator).where(Operator.id == op_result.id))
    ).scalar_one()
    assert operator_after.pin_hash != old_hash
    assert verify_password("5678", operator_after.pin_hash) is True


async def test_get_operators_returns_created(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Paul", last_name="Bernard", pin_code="4321")
    await create_operator(payload, test_db, seed.ctx)

    result = await get_operators(test_db, seed.ctx)
    last_names = {op.last_name for op in result.items}
    assert "Bernard" in last_names


async def test_soft_delete_operator_deactivates(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Marc", last_name="Petit", pin_code="0000")
    op = await create_operator(payload, test_db, seed.ctx)

    await soft_delete_operator(op.id, test_db, seed.ctx)

    operator = (await test_db.execute(select(Operator).where(Operator.id == op.id))).scalar_one()
    assert operator.is_active is False


# ── Access guards ─────────────────────────────────────────────────────────────


async def test_ensure_admin_org_access_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        await ensure_admin_org_access(test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


# ── Users ─────────────────────────────────────────────────────────────────────


async def test_list_users_returns_assigned_collaborators(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await list_users(test_db, seed.ctx)
    emails = {u.email for u in result}
    assert seed.manager.email in emails
    assert seed.operator.email in emails


async def test_list_users_non_manager_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_manager_ctx = make_establishment_ctx(seed.org, seed.est, seed.operator, is_org_admin=False)
    with pytest.raises(HTTPException) as exc_info:
        await list_users(test_db, non_manager_ctx)
    assert exc_info.value.status_code == 403


async def test_create_user_creates_and_assigns(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Moreau",
        first_name="Claire",
        email="claire.moreau@test.com",
        password="SecurePass123!",
        pin_code="7890",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    result = await create_user(payload, test_db, seed.ctx)
    assert result.user_id is not None
    assert str(result.email) == "claire.moreau@test.com"
    assert seed.est.id in result.establishment_ids


async def test_create_user_duplicate_email_raises_400(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Dupont",
        first_name="Jean",
        email=seed.manager.email,  # already exists
        password="SecurePass123!",
        pin_code="1111",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_user(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 400


async def test_create_user_unknown_role_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Test",
        first_name="User",
        email="new.user@test.com",
        password="SecurePass123!",
        pin_code="9999",
        role_id=uuid.uuid4(),  # non-existent role
        establishment_ids=[seed.est.id],
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_user(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_create_user_invalid_establishment_raises_400(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Test",
        first_name="User",
        email="user.invalid.est@test.com",
        password="SecurePass123!",
        pin_code="2222",
        role_id=seed.operator_role.id,
        establishment_ids=[uuid.uuid4()],  # non-existent establishment
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_user(payload, test_db, seed.ctx)
    assert exc_info.value.status_code == 400


# ── Operator update ───────────────────────────────────────────────────────────


async def test_update_operator_name(test_db: AsyncSession):
    from app.modules.personnel.schemas import OperatorUpdate

    seed = await make_base_seed(test_db)
    payload = OperatorCreate(first_name="Ancien", last_name="Nom", pin_code="1234")
    op = await create_operator(payload, test_db, seed.ctx)

    result = await update_operator(op.id, OperatorUpdate(first_name="Nouveau"), test_db, seed.ctx)
    assert result.first_name == "Nouveau"


async def test_update_operator_not_found_raises_404(test_db: AsyncSession):
    from app.modules.personnel.schemas import OperatorUpdate

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await update_operator(uuid.uuid4(), OperatorUpdate(first_name="Inconnu"), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


# ── update_user ───────────────────────────────────────────────────────────────


async def test_update_user_name(test_db: AsyncSession):
    from app.modules.personnel.schemas import UserUpdateRequest
    from app.modules.personnel.service import update_user

    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Ancien",
        first_name="Prénom",
        email="update.target@test.com",
        password="SecurePass123!",
        pin_code="1234",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    created = await create_user(payload, test_db, seed.ctx)

    result = await update_user(
        created.user_id, UserUpdateRequest(last_name="Nouveau"), test_db, seed.ctx
    )
    assert result.last_name == "Nouveau"


async def test_update_user_not_found_raises_404(test_db: AsyncSession):
    from app.modules.personnel.schemas import UserUpdateRequest
    from app.modules.personnel.service import update_user

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await update_user(uuid.uuid4(), UserUpdateRequest(last_name="X"), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_update_user_duplicate_email_raises_400(test_db: AsyncSession):
    from app.modules.personnel.schemas import UserUpdateRequest
    from app.modules.personnel.service import update_user

    seed = await make_base_seed(test_db)
    # Try to set email to one that's already taken (the manager's email)
    payload = UserCreateRequest(
        last_name="Test",
        first_name="User",
        email="original.email@test.com",
        password="SecurePass123!",
        pin_code="5678",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    created = await create_user(payload, test_db, seed.ctx)

    with pytest.raises(HTTPException) as exc_info:
        await update_user(
            created.user_id,
            UserUpdateRequest(email=seed.manager.email),
            test_db,
            seed.ctx,
        )
    assert exc_info.value.status_code == 400


# ── delete_user ───────────────────────────────────────────────────────────────


async def test_delete_user_soft_delete(test_db: AsyncSession):
    from sqlalchemy import select

    from app.modules.personnel.models import Utilisateur
    from app.modules.personnel.service import delete_user

    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Supprimable",
        first_name="User",
        email="to.delete@test.com",
        password="SecurePass123!",
        pin_code="4321",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    created = await create_user(payload, test_db, seed.ctx)

    await delete_user(created.user_id, test_db, seed.ctx)

    row = (
        await test_db.execute(select(Utilisateur).where(Utilisateur.id == created.user_id))
    ).scalar_one()
    assert row.deleted_at is not None


async def test_delete_user_not_found_raises_404(test_db: AsyncSession):
    from app.modules.personnel.service import delete_user

    seed = await make_base_seed(test_db)
    with pytest.raises(HTTPException) as exc_info:
        await delete_user(uuid.uuid4(), test_db, seed.ctx)
    assert exc_info.value.status_code == 404


async def test_update_user_role_rebuilds_assignments(test_db: AsyncSession):
    """Covers the 'should_rebuild' branch in update_user when role_id changes."""
    from app.modules.personnel.schemas import UserUpdateRequest
    from app.modules.personnel.service import update_user

    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Teston",
        first_name="Jean",
        email="jean.teston@test.com",
        password="SecurePass123!",
        pin_code="3456",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    created = await create_user(payload, test_db, seed.ctx)

    # Change role — triggers the assignment rebuild path
    result = await update_user(
        created.user_id,
        UserUpdateRequest(role_id=seed.manager_role.id),
        test_db,
        seed.ctx,
    )
    assert result.role_id == seed.manager_role.id


async def test_update_user_is_active_deactivates_without_rebuild(test_db: AsyncSession):
    """Covers the elif payload.is_active branch in update_user."""
    from app.modules.personnel.schemas import UserUpdateRequest
    from app.modules.personnel.service import update_user

    seed = await make_base_seed(test_db)
    payload = UserCreateRequest(
        last_name="Deactivable",
        first_name="User",
        email="deactivable@test.com",
        password="SecurePass123!",
        pin_code="7777",
        role_id=seed.operator_role.id,
        establishment_ids=[seed.est.id],
    )
    created = await create_user(payload, test_db, seed.ctx)

    result = await update_user(
        created.user_id,
        UserUpdateRequest(is_active=False),
        test_db,
        seed.ctx,
    )
    assert result.is_active is False
