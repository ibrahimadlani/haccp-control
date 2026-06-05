"""Integration tests for app/modules/auth/service.py."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.schemas import ManagerLoginRequest, OrganisationLoginRequest
from app.modules.auth.service import (
    list_operators_for_current_establishment,
    login_manager,
    login_organization,
    read_current_operator,
    read_establishment_public_metadata,
)
from tests.integration.conftest import (
    make_base_seed,
    make_establishment,
    make_organisation,
)

# ── Manager login ─────────────────────────────────────────────────────────────


async def test_login_manager_valid_credentials_returns_token(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    # The org admin email is set on the organisation
    # Use the manager's credentials and the establishment
    payload = ManagerLoginRequest(
        email=seed.manager.email,
        password="UserPassword123",
        etablissement_id=seed.est.id,
    )
    result = await login_manager(payload, test_db)
    assert result.access_token is not None
    assert result.establishment.etablissement_id == seed.est.id


async def test_login_manager_wrong_password_raises_401(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = ManagerLoginRequest(
        email=seed.manager.email,
        password="WrongPassword123",
        etablissement_id=seed.est.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_manager(payload, test_db)
    assert exc_info.value.status_code == 401


async def test_login_manager_unknown_email_raises_401(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = ManagerLoginRequest(
        email="nobody@example.com",
        password="UserPassword123",
        etablissement_id=seed.est.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_manager(payload, test_db)
    assert exc_info.value.status_code == 401


async def test_login_manager_operator_not_assigned_to_establishment_raises_401_or_403(
    test_db: AsyncSession,
):
    seed = await make_base_seed(test_db)
    # Create a second establishment; the manager is not assigned there
    other_est = await make_establishment(test_db, seed.org, nom_site="Autre site")

    payload = ManagerLoginRequest(
        email=seed.manager.email,
        password="UserPassword123",
        etablissement_id=other_est.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_manager(payload, test_db)
    assert exc_info.value.status_code in (401, 403)


async def test_login_manager_org_admin_sets_is_org_admin_claim(test_db: AsyncSession):
    """Manager whose email matches org.admin_login_email gets is_org_admin=True in token."""
    seed = await make_base_seed(test_db)
    # Set manager as the org admin
    seed.org.admin_login_email = seed.manager.email
    await test_db.flush()

    payload = ManagerLoginRequest(
        email=seed.manager.email,
        password="UserPassword123",
        etablissement_id=seed.est.id,
    )
    result = await login_manager(payload, test_db)
    assert result.establishment.is_org_admin is True


# ── Organisation login ────────────────────────────────────────────────────────


async def test_login_organization_valid_credentials_returns_token(test_db: AsyncSession):
    await make_organisation(
        test_db,
        admin_email="org_admin@test.com",
        admin_password="OrgPassword123",
    )
    payload = OrganisationLoginRequest(
        email="org_admin@test.com",
        password="OrgPassword123",
    )
    result = await login_organization(payload, test_db)
    assert result.access_token is not None


async def test_login_organization_wrong_password_raises_401(test_db: AsyncSession):
    await make_organisation(
        test_db,
        admin_email="org_admin2@test.com",
        admin_password="OrgPassword123",
    )
    payload = OrganisationLoginRequest(
        email="org_admin2@test.com",
        password="WrongPassword123",
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_organization(payload, test_db)
    assert exc_info.value.status_code == 401


async def test_login_organization_unknown_email_raises_401(test_db: AsyncSession):
    payload = OrganisationLoginRequest(
        email="ghost@test.com",
        password="SomePassword123",
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_organization(payload, test_db)
    assert exc_info.value.status_code == 401


# ── Establishment public metadata ─────────────────────────────────────────────


async def test_read_establishment_public_metadata_returns_site_info(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await read_establishment_public_metadata(str(seed.est.id), test_db)
    assert result.etablissement_id == seed.est.id
    assert result.nom_site == seed.est.nom_site
    assert result.timezone == seed.est.timezone


async def test_read_establishment_public_metadata_not_found_raises_404(test_db: AsyncSession):
    with pytest.raises(HTTPException) as exc_info:
        await read_establishment_public_metadata(str(uuid.uuid4()), test_db)
    assert exc_info.value.status_code == 404


async def test_login_manager_establishment_not_found_raises_404(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    payload = ManagerLoginRequest(
        email=seed.manager.email,
        password="UserPassword123",
        etablissement_id=uuid.uuid4(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await login_manager(payload, test_db)
    assert exc_info.value.status_code == 404


# ── read_current_operator ─────────────────────────────────────────────────────


async def test_read_current_operator_returns_operator_payload(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await read_current_operator(seed.ctx, seed.operator, test_db)

    assert result["operator"]["id"] == str(seed.operator.id)
    assert result["operator"]["nom"] == seed.operator.nom
    assert result["establishment"]["id"] == str(seed.est.id)


async def test_read_current_operator_manager_is_admin(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await read_current_operator(seed.ctx, seed.manager, test_db)
    assert result["operator"]["is_admin"] is True


# ── list_operators_for_current_establishment ──────────────────────────────────


async def test_list_operators_for_establishment_returns_assigned_users(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await list_operators_for_current_establishment(seed.ctx, test_db)
    user_ids = {str(op.id) for op in result}
    assert str(seed.operator.id) in user_ids


async def test_list_operators_sorted_alphabetically(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    result = await list_operators_for_current_establishment(seed.ctx, test_db)
    noms = [op.nom for op in result]
    assert noms == sorted(noms, key=str.lower)
