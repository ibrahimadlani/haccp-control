"""E2E tests for the Production domain."""

from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.core.time_utils import now_for_site
from app.modules.nonconformities.models import NonConformity, WorkflowType
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.production.models import ProductionStep, StepType
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class ProductionSeed:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    operator: Utilisateur


@pytest.fixture
async def seed_production(test_db: AsyncSession) -> ProductionSeed:
    manager_email = "production.manager@test.com"
    org = Organisation(
        nom_entite="Production Test Org",
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=manager_email,
        admin_password_hash=get_password_hash("ProdPass123!"),
    )
    test_db.add(org)
    await test_db.flush()

    est = Etablissement(
        organisation_id=org.id, nom_site="Production Site", timezone="Europe/Paris"
    )
    manager_role = Role(
        nom_role="MANAGER_PROD", permissions={"manager": True, "can_manage_device_login": True}
    )
    operator_role = Role(nom_role="OPERATEUR_PROD", permissions={})
    test_db.add_all([est, manager_role, operator_role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Prod",
        prenom="Manager",
        email=manager_email,
        mot_de_passe_hash=get_password_hash("ProdPass123!"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Prod",
        prenom="Operator",
        email="production.operator@test.com",
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
    return ProductionSeed(
        organisation=org,
        etablissement=est,
        manager=manager,
        operator=operator,
    )


async def _login(client: AsyncClient, seed: ProductionSeed) -> str:
    resp = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "ProdPass123!",
            "etablissement_id": str(seed.etablissement.id),
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _count_temperature_ncs(
    test_db: AsyncSession, establishment_id
) -> int:
    result = await test_db.execute(
        select(func.count())
        .select_from(NonConformity)
        .where(
            NonConformity.establishment_id == establishment_id,
            NonConformity.workflow_type == WorkflowType.TEMPERATURE,
        )
    )
    return result.scalar_one()


async def _create_batch(
    client: AsyncClient,
    headers: dict,
    *,
    nom_recette: str = "Test",
    food_type: str = "AUTRE",
) -> str:
    resp = await client.post(
        "/api/v1/production-batches",
        json={
            "nom_recette": nom_recette,
            "food_type": food_type,
            "date_production": date.today().isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_and_list_production_batches(
    client: AsyncClient, seed_production: ProductionSeed
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/v1/production-batches",
        json={
            "nom_recette": "Soupe du jour",
            "food_type": "LEGUMES_FECULENTS",
            "date_production": date.today().isoformat(),
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    batch = create_resp.json()
    assert batch["nom_recette"] == "Soupe du jour"
    assert batch["food_type"] == "LEGUMES_FECULENTS"
    assert batch["statut"] == "EN_COURS"
    assert batch["etablissement_id"] == str(seed_production.etablissement.id)

    list_resp = await client.get("/api/v1/production-batches", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == batch["id"]


async def test_create_and_list_production_steps(
    client: AsyncClient, seed_production: ProductionSeed
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}
    batch_id = await _create_batch(client, headers, nom_recette="Risotto")

    step_resp = await client.post(
        f"/api/v1/production-batches/{batch_id}/steps",
        json={
            "step_type": "CUISSON_A_COEUR",
            "temperature_mesuree": 85.5,
            "operator_id": str(seed_production.operator.id),
        },
        headers=headers,
    )
    assert step_resp.status_code == 201
    step = step_resp.json()
    assert step["step_type"] == "CUISSON_A_COEUR"
    assert step["temperature_mesuree"] == 85.5
    assert step["operator_id"] == str(seed_production.operator.id)
    assert step["batch_id"] == batch_id

    list_resp = await client.get(
        f"/api/v1/production-batches/{batch_id}/steps",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1


async def test_production_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/production-batches")
    assert resp.status_code == 401


async def test_cuisson_non_conforme_cree_ticket(
    client: AsyncClient,
    seed_production: ProductionSeed,
    test_db: AsyncSession,
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}
    batch_id = await _create_batch(client, headers, food_type="VIANDE_HACHEE")

    before = await _count_temperature_ncs(test_db, seed_production.etablissement.id)

    step_resp = await client.post(
        f"/api/v1/production-batches/{batch_id}/steps",
        json={
            "step_type": "CUISSON_A_COEUR",
            "temperature_mesuree": 54.0,
            "operator_id": str(seed_production.operator.id),
        },
        headers=headers,
    )
    assert step_resp.status_code == 201

    after = await _count_temperature_ncs(test_db, seed_production.etablissement.id)
    assert after == before + 1


async def test_refroidissement_trop_lent_cree_ticket(
    client: AsyncClient,
    seed_production: ProductionSeed,
    test_db: AsyncSession,
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}
    batch_id = await _create_batch(client, headers)

    debut_ts = now_for_site(seed_production.etablissement.timezone) - timedelta(minutes=130)
    test_db.add(
        ProductionStep(
            batch_id=batch_id,
            step_type=StepType.REFROIDISSEMENT_DEBUT,
            temperature_mesuree=63.0,
            timestamp=debut_ts,
            operator_id=seed_production.operator.id,
        )
    )
    await test_db.commit()

    before = await _count_temperature_ncs(test_db, seed_production.etablissement.id)

    step_resp = await client.post(
        f"/api/v1/production-batches/{batch_id}/steps",
        json={
            "step_type": "REFROIDISSEMENT_FIN",
            "temperature_mesuree": 8.0,
            "operator_id": str(seed_production.operator.id),
        },
        headers=headers,
    )
    assert step_resp.status_code == 201

    after = await _count_temperature_ncs(test_db, seed_production.etablissement.id)
    assert after == before + 1


async def test_cuisson_volaille_non_conforme(
    client: AsyncClient,
    seed_production: ProductionSeed,
    test_db: AsyncSession,
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}
    batch_id = await _create_batch(client, headers, food_type="VOLAILLE")

    before = await _count_temperature_ncs(test_db, seed_production.etablissement.id)

    step_resp = await client.post(
        f"/api/v1/production-batches/{batch_id}/steps",
        json={
            "step_type": "CUISSON_A_COEUR",
            "temperature_mesuree": 70.0,
            "operator_id": str(seed_production.operator.id),
        },
        headers=headers,
    )
    assert step_resp.status_code == 201

    after = await _count_temperature_ncs(test_db, seed_production.etablissement.id)
    assert after == before + 1


async def test_cuisson_viande_piece_conforme_sans_ticket(
    client: AsyncClient,
    seed_production: ProductionSeed,
    test_db: AsyncSession,
):
    token = await _login(client, seed_production)
    headers = {"Authorization": f"Bearer {token}"}
    batch_id = await _create_batch(client, headers, food_type="VIANDE_PIECE")

    before = await _count_temperature_ncs(test_db, seed_production.etablissement.id)

    step_resp = await client.post(
        f"/api/v1/production-batches/{batch_id}/steps",
        json={
            "step_type": "CUISSON_A_COEUR",
            "temperature_mesuree": 60.0,
            "operator_id": str(seed_production.operator.id),
        },
        headers=headers,
    )
    assert step_resp.status_code == 201

    after = await _count_temperature_ncs(test_db, seed_production.etablissement.id)
    assert after == before
