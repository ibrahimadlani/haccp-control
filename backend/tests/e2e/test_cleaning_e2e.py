"""E2E tests for the Cleaning domain."""

from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class CleaningSeed:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    operator: Utilisateur
    manager_role: Role
    operator_role: Role


@pytest.fixture
async def seed_cleaning(test_db: AsyncSession) -> CleaningSeed:
    manager_email = "cleaning.manager@test.com"
    org = Organisation(
        nom_entite="Cleaning Test Org",
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=manager_email,
        admin_password_hash=get_password_hash("CleanPass123!"),
    )
    test_db.add(org)
    await test_db.flush()

    est = Etablissement(organisation_id=org.id, nom_site="Cleaning Site", timezone="Europe/Paris")
    manager_role = Role(
        nom_role="MANAGER_CL", permissions={"manager": True, "can_manage_device_login": True}
    )
    operator_role = Role(nom_role="OPERATEUR_CL", permissions={})
    test_db.add_all([est, manager_role, operator_role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Clean",
        prenom="Manager",
        email=manager_email,
        mot_de_passe_hash=get_password_hash("CleanPass123!"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Clean",
        prenom="Operator",
        email="cleaning.operator@test.com",
        mot_de_passe_hash=get_password_hash("OpPass123!"),
        code_pin=get_password_hash("2222"),
    )
    test_db.add_all([manager, operator])
    await test_db.flush()
    test_db.add_all(
        [
            AffectationSite(
                utilisateur_id=manager.id, etablissement_id=est.id, role_id=manager_role.id
            ),
            AffectationSite(
                utilisateur_id=operator.id, etablissement_id=est.id, role_id=operator_role.id
            ),
        ]
    )
    await test_db.commit()
    return CleaningSeed(
        organisation=org,
        etablissement=est,
        manager=manager,
        operator=operator,
        manager_role=manager_role,
        operator_role=operator_role,
    )


async def _login(client: AsyncClient, seed: CleaningSeed) -> str:
    resp = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "CleanPass123!",
            "etablissement_id": str(seed.etablissement.id),
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_create_cleaning_zone(client: AsyncClient, seed_cleaning: CleaningSeed):
    token = await _login(client, seed_cleaning)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/cleaning-zones",
        json={"name": "Cuisine froide"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Cuisine froide"


async def test_create_cleaning_routine(client: AsyncClient, seed_cleaning: CleaningSeed):
    token = await _login(client, seed_cleaning)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/cleaning-routines",
        json={"name": "Ouverture", "schedule_type": "OPENING"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Ouverture"
    return data["id"]


async def test_create_task_template(client: AsyncClient, seed_cleaning: CleaningSeed):
    token = await _login(client, seed_cleaning)
    headers = {"Authorization": f"Bearer {token}"}

    zone_resp = await client.post(
        "/api/v1/cleaning-zones",
        json={"name": "Zone Task"},
        headers=headers,
    )
    zone_id = zone_resp.json()["id"]

    routine_resp = await client.post(
        "/api/v1/cleaning-routines",
        json={"name": "Routine Task", "schedule_type": "OPENING"},
        headers=headers,
    )
    routine_id = routine_resp.json()["id"]

    task_resp = await client.post(
        f"/api/v1/cleaning-routines/{routine_id}/tasks",
        json={"zone_id": zone_id, "name": "Nettoyer les planches"},
        headers=headers,
    )
    assert task_resp.status_code == 201
    assert task_resp.json()["name"] == "Nettoyer les planches"


async def test_get_current_routine(client: AsyncClient, seed_cleaning: CleaningSeed):
    token = await _login(client, seed_cleaning)
    headers = {"Authorization": f"Bearer {token}"}

    # Create a routine first
    zone_resp = await client.post(
        "/api/v1/cleaning-zones",
        json={"name": "Zone Current"},
        headers=headers,
    )
    assert zone_resp.status_code == 201
    await client.post(
        "/api/v1/cleaning-routines",
        json={"name": "Routine Current", "schedule_type": "OPENING"},
        headers=headers,
    )

    resp = await client.get("/api/v1/cleaning-routines/current", headers=headers)
    assert resp.status_code == 200


async def test_bulk_cleaning_logs(client: AsyncClient, seed_cleaning: CleaningSeed):
    token = await _login(client, seed_cleaning)
    headers = {"Authorization": f"Bearer {token}"}

    zone_resp = await client.post(
        "/api/v1/cleaning-zones",
        json={"name": "Zone Bulk"},
        headers=headers,
    )
    zone_id = zone_resp.json()["id"]

    routine_resp = await client.post(
        "/api/v1/cleaning-routines",
        json={"name": "Routine Bulk", "schedule_type": "OPENING"},
        headers=headers,
    )
    routine_id = routine_resp.json()["id"]

    task_resp = await client.post(
        f"/api/v1/cleaning-routines/{routine_id}/tasks",
        json={"zone_id": zone_id, "name": "Tâche bulk"},
        headers=headers,
    )
    task_id = task_resp.json()["id"]

    log_resp = await client.post(
        "/api/v1/cleaning-logs/bulk",
        json={"items": [{"task_id": task_id, "status": "DONE"}]},
        headers={
            **headers,
            "X-Device-Pin": "2222",
            "X-Operator-Id": str(seed_cleaning.operator.id),
        },
    )
    assert log_resp.status_code == 201
    assert log_resp.json()["count"] == 1
