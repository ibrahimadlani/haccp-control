"""Integration tests for app/modules/auth/service.py."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.schemas import ManagerLoginRequest, OrganisationLoginRequest
from app.modules.auth.service import login_manager, login_organization
from tests.integration.conftest import (
    make_base_seed,
    make_establishment,
    make_organisation,
    make_role,
    make_user,
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
    assert result.token is not None
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


async def test_login_manager_operator_not_assigned_to_establishment_raises_401_or_403(test_db: AsyncSession):
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
    org = await make_organisation(
        test_db,
        admin_email="org_admin@test.com",
        admin_password="OrgPassword123",
    )
    payload = OrganisationLoginRequest(
        email="org_admin@test.com",
        password="OrgPassword123",
    )
    result = await login_organization(payload, test_db)
    assert result.token is not None


async def test_login_organization_wrong_password_raises_401(test_db: AsyncSession):
    org = await make_organisation(
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
