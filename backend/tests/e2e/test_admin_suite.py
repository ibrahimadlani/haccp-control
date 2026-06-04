from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password
from app.models import (
    ActionCorrective,
    AffectationSite,
    Equipement,
    Etablissement,
    NonConformity,
    NonConformityStatus,
    ReleveTemperature,
    Role,
    SourceReleve,
    TypeEquipement,
    Utilisateur,
    WorkflowType,
)
from app.modules.tenant.models import Organisation, TypeSecteur


@dataclass(frozen=True)
class AdminSuiteSeed:
    organisation: Organisation
    etablissement_1: Etablissement
    etablissement_2: Etablissement
    manager_role: Role
    operator_role: Role
    manager: Utilisateur


@pytest.fixture(scope="function")
async def seed_admin_suite_data(test_db: AsyncSession) -> AdminSuiteSeed:
    organisation = Organisation(
        nom_entite="Organisation Admin Suite",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="ORG-ADMIN-SUITE",
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
        email="suite.manager@example.com",
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

    equipment = Equipement(
        etablissement_id=etablissement_1.id,
        nom="Vitrine test",
        type_equipement=TypeEquipement.VITRINE_REFRIGEREE,
        temperature_min_cible=1,
        temperature_max_cible=4,
    )
    test_db.add(equipment)

    await test_db.commit()

    return AdminSuiteSeed(
        organisation=organisation,
        etablissement_1=etablissement_1,
        etablissement_2=etablissement_2,
        manager_role=manager_role,
        operator_role=operator_role,
        manager=manager,
    )


async def _manager_token(client: AsyncClient, seed: AdminSuiteSeed) -> str:
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
async def test_create_operator_hashes_pin_and_password(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    payload = {
        "last_name": "Durand",
        "first_name": "Karim",
        "email": "suite.operator@example.com",
        "password": "StrongPassw0rd!",
        "pin_code": "4827",
        "role_id": str(seed_admin_suite_data.operator_role.id),
        "establishment_ids": [
            str(seed_admin_suite_data.etablissement_1.id),
            str(seed_admin_suite_data.etablissement_2.id),
        ],
    }

    response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201

    user_result = await test_db.execute(
        select(Utilisateur)
        .options(selectinload(Utilisateur.affectations))
        .where(Utilisateur.email == payload["email"])
    )
    user = user_result.scalar_one_or_none()

    assert user is not None
    assert user.code_pin is not None
    assert user.code_pin.startswith("$2b$")
    assert user.mot_de_passe_hash.startswith("$2b$")
    assert verify_password(payload["pin_code"], user.code_pin)
    assert verify_password(payload["password"], user.mot_de_passe_hash)
    assert len(user.affectations) == 2


@pytest.mark.asyncio
async def test_create_equipement_rejects_incoherent_temperature_range(
    client: AsyncClient,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    response = await client.post(
        "/api/v1/equipments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Chambre froide incoherente",
            "equipment_type": "CHAMBRE_FROIDE_POSITIVE",
            "min_target_temperature": 8.0,
            "max_target_temperature": 2.0,
            "establishment_id": str(seed_admin_suite_data.etablissement_1.id),
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_listings_do_not_raise_async_loading_errors(
    client: AsyncClient,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    users_response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert users_response.status_code == 200
    assert isinstance(users_response.json(), list)

    equipment_response = await client.get(
        "/api/v1/equipments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert equipment_response.status_code == 200
    body = equipment_response.json()
    assert "items" in body
    assert isinstance(body["items"], list)

    roles_response = await client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert roles_response.status_code == 200
    assert isinstance(roles_response.json(), list)


@pytest.mark.asyncio
async def test_update_user_profile_role_sites_and_pin(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    create_payload = {
        "last_name": "Initial",
        "first_name": "Operateur",
        "email": "suite.update@example.com",
        "password": "StrongPassw0rd!",
        "pin_code": "4827",
        "role_id": str(seed_admin_suite_data.operator_role.id),
        "establishment_ids": [
            str(seed_admin_suite_data.etablissement_1.id),
            str(seed_admin_suite_data.etablissement_2.id),
        ],
    }
    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json=create_payload,
    )
    assert create_response.status_code == 201
    created_user_id = create_response.json()["user_id"]

    update_response = await client.patch(
        f"/api/v1/users/{created_user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "MisAJour",
            "first_name": "Collaborateur",
            "email": "suite.updated@example.com",
            "pin_code": "7531",
            "role_id": str(seed_admin_suite_data.manager_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
            "is_active": False,
        },
    )
    assert update_response.status_code == 200

    user_result = await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == created_user_id)
    )
    user = user_result.scalar_one()

    assert user.nom == "MisAJour"
    assert user.prenom == "Collaborateur"
    assert user.email == "suite.updated@example.com"
    assert user.code_pin is not None
    assert user.code_pin.startswith("$2b$")
    assert verify_password("7531", user.code_pin)

    assignments_result = await test_db.execute(
        select(AffectationSite).where(AffectationSite.utilisateur_id == user.id)
    )
    assignments = assignments_result.scalars().all()

    assert len(assignments) == 1
    assignment = assignments[0]
    assert assignment.etablissement_id == seed_admin_suite_data.etablissement_1.id
    assert assignment.role_id == seed_admin_suite_data.manager_role.id
    assert assignment.is_active is False


@pytest.mark.asyncio
async def test_update_user_rejects_duplicate_email(
    client: AsyncClient,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    first_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Alpha",
            "first_name": "One",
            "email": "alpha@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "4827",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert first_response.status_code == 201

    second_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Beta",
            "first_name": "Two",
            "email": "beta@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "7531",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert second_response.status_code == 201

    second_user_id = second_response.json()["user_id"]
    duplicate_update_response = await client.patch(
        f"/api/v1/users/{second_user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "alpha@example.com"},
    )

    assert duplicate_update_response.status_code == 400
    assert duplicate_update_response.json()["detail"] == "Email already used."


@pytest.mark.asyncio
async def test_update_user_status_with_generic_patch_endpoint(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Status",
            "first_name": "Target",
            "email": "status.target@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "4827",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]

    disable_response = await client.patch(
        f"/api/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": False},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["is_active"] is False

    assignments_result = await test_db.execute(
        select(AffectationSite).where(AffectationSite.utilisateur_id == user_id)
    )
    assignments = assignments_result.scalars().all()
    assert assignments
    assert all(assignment.is_active is False for assignment in assignments)


@pytest.mark.asyncio
async def test_delete_user_soft_marks_deleted_and_deactivates_assignments(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Delete",
            "first_name": "Soft",
            "email": "delete.soft@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "4827",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]

    delete_response = await client.delete(
        f"/api/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204

    user_result = await test_db.execute(select(Utilisateur).where(Utilisateur.id == user_id))
    user = user_result.scalar_one()
    assert user.deleted_at is not None

    assignments_result = await test_db.execute(
        select(AffectationSite).where(AffectationSite.utilisateur_id == user_id)
    )
    assignments = assignments_result.scalars().all()
    assert assignments
    assert all(assignment.is_active is False for assignment in assignments)


@pytest.mark.asyncio
async def test_delete_user_hard_requires_platform_admin(
    client: AsyncClient,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Delete",
            "first_name": "HardBlocked",
            "email": "delete.hard.blocked@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "4827",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]

    delete_response = await client.delete(
        f"/api/v1/users/{user_id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 403
    assert (
        delete_response.json()["detail"] == "Hard delete is restricted to platform administrators."
    )


@pytest.mark.asyncio
async def test_delete_user_hard_succeeds_for_platform_admin(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    seed_admin_suite_data.manager_role.permissions = {
        "manager": True,
        "can_manage_device_login": True,
        "platform_admin": True,
    }
    await test_db.commit()

    token = await _manager_token(client, seed_admin_suite_data)

    create_response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "last_name": "Delete",
            "first_name": "HardAllowed",
            "email": "delete.hard.allowed@example.com",
            "password": "StrongPassw0rd!",
            "pin_code": "4827",
            "role_id": str(seed_admin_suite_data.operator_role.id),
            "establishment_ids": [str(seed_admin_suite_data.etablissement_1.id)],
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["user_id"]

    delete_response = await client.delete(
        f"/api/v1/users/{user_id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204

    deleted_user_result = await test_db.execute(
        select(Utilisateur).where(Utilisateur.id == user_id)
    )
    assert deleted_user_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_equipment_soft_then_hard_with_authorization(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    equipment_response = await client.post(
        "/api/v1/equipments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "A supprimer",
            "equipment_type": "CHAMBRE_FROIDE_POSITIVE",
            "min_target_temperature": 1.0,
            "max_target_temperature": 4.0,
            "establishment_id": str(seed_admin_suite_data.etablissement_1.id),
        },
    )
    assert equipment_response.status_code == 201
    equipment_id = equipment_response.json()["id"]

    soft_delete = await client.delete(
        f"/api/v1/equipments/{equipment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert soft_delete.status_code == 204

    forbidden_hard_delete = await client.delete(
        f"/api/v1/equipments/{equipment_id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden_hard_delete.status_code == 403
    assert (
        forbidden_hard_delete.json()["detail"]
        == "Hard delete is restricted to platform administrators."
    )

    seed_admin_suite_data.manager_role.permissions = {
        "manager": True,
        "can_manage_device_login": True,
        "platform_admin": True,
    }
    await test_db.commit()

    allowed_hard_delete = await client.delete(
        f"/api/v1/equipments/{equipment_id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert allowed_hard_delete.status_code == 204

    equipment_result = await test_db.execute(
        select(Equipement).where(Equipement.id == equipment_id)
    )
    assert equipment_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_admin_alerts_list_and_stats(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_admin_suite_data: AdminSuiteSeed,
) -> None:
    token = await _manager_token(client, seed_admin_suite_data)

    equipement_result = await test_db.execute(
        select(Equipement).where(
            Equipement.etablissement_id == seed_admin_suite_data.etablissement_1.id
        )
    )
    equipement = equipement_result.scalar_one()

    releve = ReleveTemperature(
        etablissement_id=seed_admin_suite_data.etablissement_1.id,
        equipement_id=equipement.id,
        utilisateur_id=seed_admin_suite_data.manager.id,
        valeur_mesuree=10,
        is_conforme=False,
        source=SourceReleve.MANUEL,
        mesure_effectuee_at=datetime.now(UTC),
    )
    test_db.add(releve)
    await test_db.flush()

    nc = NonConformity(
        establishment_id=seed_admin_suite_data.etablissement_1.id,
        workflow_type=WorkflowType.TEMPERATURE,
        status=NonConformityStatus.RESOLVED,
        source_record_id=releve.id,
        opened_by_id=seed_admin_suite_data.manager.id,
        opened_at=datetime.now(UTC),
        resolved_at=datetime.now(UTC),
    )
    test_db.add(nc)
    await test_db.flush()

    action = ActionCorrective(
        nonconformity_id=nc.id,
        utilisateur_id=seed_admin_suite_data.manager.id,
        description="Refroidissement relancé et produit isolé.",
        signee_at=datetime.now(UTC),
    )
    test_db.add(action)
    await test_db.commit()

    alerts_response = await client.get(
        "/api/v1/nonconformities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert alerts_response.status_code == 200
    alerts_body = alerts_response.json()
    assert isinstance(alerts_body.get("items"), list)
    assert alerts_body["total_resolved"] >= 1

    stats_response = await client.get(
        "/api/v1/nonconformities/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stats_response.status_code == 200
    stats_body = stats_response.json()
    assert stats_body["total"] >= 1
    assert stats_body["total_resolved"] >= 1
