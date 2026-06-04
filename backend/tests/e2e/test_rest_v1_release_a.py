from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class SeedData:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur


@pytest.fixture(scope="function")
async def seed_rest_v1_data(test_db: AsyncSession) -> SeedData:
    organisation = Organisation(
        nom_entite="REST v1 Org",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="REST-V1-001",
        admin_login_email="restv1.owner@test.com",
        admin_password_hash=get_password_hash("OrgOwnerPass123!"),
    )
    test_db.add(organisation)
    await test_db.flush()

    etablissement = Etablissement(
        organisation_id=organisation.id,
        nom_site="REST v1 Site",
        timezone="Europe/Paris",
    )
    manager_role = Role(
        nom_role="MANAGER",
        permissions={"manager": True, "can_manage_device_login": True},
    )
    manager = Utilisateur(
        nom="Manager",
        prenom="ReleaseA",
        email="restv1.manager@test.com",
        mot_de_passe_hash=get_password_hash("ValidPassword123"),
        code_pin=get_password_hash("1111"),
    )
    test_db.add_all([etablissement, manager_role, manager])
    await test_db.flush()

    test_db.add(
        AffectationSite(
            utilisateur_id=manager.id,
            etablissement_id=etablissement.id,
            role_id=manager_role.id,
            is_active=True,
        )
    )
    await test_db.commit()

    return SeedData(organisation=organisation, etablissement=etablissement, manager=manager)


@pytest.mark.asyncio
async def test_old_manager_login_endpoint_is_removed(
    client: AsyncClient,
    seed_rest_v1_data: SeedData,
) -> None:
    response = await client.post(
        "/api/v1/auth/login/manager",
        json={
            "email": seed_rest_v1_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_rest_v1_data.etablissement.id),
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_new_establishment_sessions_route_works(
    client: AsyncClient,
    seed_rest_v1_data: SeedData,
) -> None:
    response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_rest_v1_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_rest_v1_data.etablissement.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert payload["establishment"]["etablissement_id"] == str(seed_rest_v1_data.etablissement.id)


@pytest.mark.asyncio
async def test_new_users_route_alias_works(
    client: AsyncClient,
    seed_rest_v1_data: SeedData,
) -> None:
    login = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_rest_v1_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_rest_v1_data.etablissement.id),
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
