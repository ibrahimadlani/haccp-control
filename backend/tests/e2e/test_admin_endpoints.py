from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class AdminSeedData:
    organisation: Organisation
    etablissement_1: Etablissement
    etablissement_2: Etablissement
    manager_role: Role
    operator_role: Role
    manager: Utilisateur


@pytest.fixture(scope="function")
async def seed_admin_data(test_db: AsyncSession) -> AdminSeedData:
    organisation = Organisation(
        nom_entite="Organisation Admin Test",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="ORG-ADMIN-001",
    )
    test_db.add(organisation)
    await test_db.flush()

    etablissement_1 = Etablissement(
        organisation_id=organisation.id,
        nom_site="Cuisine Centrale",
        timezone="Europe/Paris",
    )
    etablissement_2 = Etablissement(
        organisation_id=organisation.id,
        nom_site="Boucherie Centre",
        timezone="Europe/Paris",
    )
    test_db.add_all([etablissement_1, etablissement_2])

    manager_role = Role(
        nom_role="MANAGER",
        permissions={"manager": True, "can_manage_device_login": True},
    )
    operator_role = Role(
        nom_role="OPERATEUR",
        permissions={"can_create_temperature_record": True},
    )
    test_db.add_all([manager_role, operator_role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Admin",
        prenom="Alice",
        email="admin.manager@example.com",
        mot_de_passe_hash=get_password_hash("ValidPassword123!"),
        code_pin=get_password_hash("1111"),
    )
    test_db.add(manager)
    await test_db.flush()

    test_db.add(
        AffectationSite(
            utilisateur_id=manager.id,
            etablissement_id=etablissement_1.id,
            role_id=manager_role.id,
            is_active=True,
        )
    )
    await test_db.commit()

    return AdminSeedData(
        organisation=organisation,
        etablissement_1=etablissement_1,
        etablissement_2=etablissement_2,
        manager_role=manager_role,
        operator_role=operator_role,
        manager=manager,
    )


async def _login_manager_token(client: AsyncClient, seed: AdminSeedData) -> str:
    response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "ValidPassword123!",
            "etablissement_id": str(seed.etablissement_1.id),
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_user_with_multi_assignment_success_and_duplicate_email(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_data: AdminSeedData,
) -> None:
    token = await _login_manager_token(client, seed_admin_data)

    payload = {
        "last_name": "Nouveau",
        "first_name": "Collaborateur",
        "email": "nouveau.collab@example.com",
        "password": "StrongPassw0rd!",
        "pin_code": "4827",
        "role_id": str(seed_admin_data.operator_role.id),
        "establishment_ids": [
            str(seed_admin_data.etablissement_1.id),
            str(seed_admin_data.etablissement_2.id),
        ],
    }

    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert create_response.status_code == 201

    created_user_result = await test_db.execute(
        select(Utilisateur)
        .options(selectinload(Utilisateur.affectations))
        .where(Utilisateur.email == payload["email"])
    )
    created_user = created_user_result.scalar_one_or_none()

    assert created_user is not None
    assert created_user.mot_de_passe_hash.startswith("$2b$")
    assert created_user.code_pin is not None
    assert created_user.code_pin.startswith("$2b$")
    assert verify_password(payload["password"], created_user.mot_de_passe_hash)
    assert verify_password(payload["pin_code"], created_user.code_pin)

    assignments_result = await test_db.execute(
        select(AffectationSite).where(
            AffectationSite.utilisateur_id == created_user.id,
            AffectationSite.is_active.is_(True),
        )
    )
    assignments = assignments_result.scalars().all()

    assert len(assignments) == 2
    assert {assignment.etablissement_id for assignment in assignments} == {
        seed_admin_data.etablissement_1.id,
        seed_admin_data.etablissement_2.id,
    }

    list_response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()

    created_row = next((row for row in rows if row["email"] == payload["email"]), None)
    assert created_row is not None
    assert created_row["last_name"] == payload["last_name"]
    assert created_row["first_name"] == payload["first_name"]
    assert created_row["role_id"] == str(seed_admin_data.operator_role.id)
    assert created_row["is_active"] is True
    assert len(created_row["sites"]) == 2
    assert {site["establishment_id"] for site in created_row["sites"]} == {
        str(seed_admin_data.etablissement_1.id),
        str(seed_admin_data.etablissement_2.id),
    }

    duplicate_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Email is already used by another collaborator."
