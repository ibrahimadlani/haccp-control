"""E2E tests for the feature flag system (require_feature dependency)."""

from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.equipments.models import Equipement
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class FeatureFlagSeed:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    operator: Utilisateur
    manager_role: Role
    operator_role: Role
    equipment: Equipement


@pytest.fixture
async def seed_ff_data(test_db: AsyncSession) -> FeatureFlagSeed:
    # Manager email matches org admin → is_org_admin=True in token
    manager_email = "ff.manager@test.com"
    org = Organisation(
        nom_entite="FF Test Org",
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=manager_email,
        admin_password_hash=get_password_hash("OrgPass123!"),
    )
    test_db.add(org)
    await test_db.flush()

    est = Etablissement(organisation_id=org.id, nom_site="FF Site", timezone="Europe/Paris")
    manager_role = Role(
        nom_role="MANAGER_FF", permissions={"manager": True, "can_manage_device_login": True}
    )
    operator_role = Role(nom_role="OPERATEUR_FF", permissions={})
    test_db.add_all([est, manager_role, operator_role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Flagman",
        prenom="Alice",
        email=manager_email,
        mot_de_passe_hash=get_password_hash("ManagerPass123!"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Opérateur",
        prenom="Bob",
        email="ff.operator@test.com",
        mot_de_passe_hash=get_password_hash("OperPass123!"),
        code_pin=get_password_hash("9999"),
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
    equip = Equipement(
        etablissement_id=est.id,
        nom="Chambre froide FF",
        temperature_min_cible=Decimal("0"),
        temperature_max_cible=Decimal("4"),
    )
    test_db.add(equip)
    await test_db.commit()
    return FeatureFlagSeed(
        organisation=org,
        etablissement=est,
        manager=manager,
        operator=operator,
        manager_role=manager_role,
        operator_role=operator_role,
        equipment=equip,
    )


async def _login(client: AsyncClient, seed: FeatureFlagSeed) -> str:
    resp = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "ManagerPass123!",
            "etablissement_id": str(seed.etablissement.id),
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── Cleaning feature toggle ───────────────────────────────────────────────────


async def test_cleaning_feature_disabled_returns_403(
    client: AsyncClient, seed_ff_data: FeatureFlagSeed
):
    token = await _login(client, seed_ff_data)
    headers = {"Authorization": f"Bearer {token}"}

    # Disable cleaning
    patch_resp = await client.patch(
        "/api/v1/establishment-settings",
        json={"cleaning": {"enabled": False}},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    # Cleaning endpoints must return 403
    routines_resp = await client.get("/api/v1/cleaning-routines", headers=headers)
    assert routines_resp.status_code == 403
    assert "cleaning" in routines_resp.json()["detail"]


async def test_cleaning_feature_re_enabled_returns_200(
    client: AsyncClient, seed_ff_data: FeatureFlagSeed
):
    token = await _login(client, seed_ff_data)
    headers = {"Authorization": f"Bearer {token}"}

    # Disable
    await client.patch(
        "/api/v1/establishment-settings",
        json={"cleaning": {"enabled": False}},
        headers=headers,
    )

    # Re-enable
    await client.patch(
        "/api/v1/establishment-settings",
        json={"cleaning": {"enabled": True}},
        headers=headers,
    )

    routines_resp = await client.get("/api/v1/cleaning-routines", headers=headers)
    assert routines_resp.status_code == 200


# ── Timeclock feature toggle ──────────────────────────────────────────────────


async def test_timeclock_disabled_blocks_clock_in(
    client: AsyncClient, seed_ff_data: FeatureFlagSeed
):
    token = await _login(client, seed_ff_data)
    headers = {"Authorization": f"Bearer {token}"}

    # Disable timeclock
    await client.patch(
        "/api/v1/establishment-settings",
        json={"timeclock": {"enabled": False}},
        headers=headers,
    )

    # POST /time-clock-events must return 403
    clock_resp = await client.post(
        "/api/v1/time-clock-events",
        json={"type_evenement": "CLOCK_IN"},
        headers={
            **headers,
            "X-Device-Pin": "9999",
            "X-Operator-Id": str(seed_ff_data.operator.id),
        },
    )
    assert clock_resp.status_code == 403


# ── Suppliers feature toggle ──────────────────────────────────────────────────


async def test_suppliers_feature_disabled_blocks_get_suppliers(
    client: AsyncClient, seed_ff_data: FeatureFlagSeed
):
    token = await _login(client, seed_ff_data)
    headers = {"Authorization": f"Bearer {token}"}

    await client.patch(
        "/api/v1/establishment-settings",
        json={"suppliers": {"enabled": False}},
        headers=headers,
    )

    resp = await client.get("/api/v1/suppliers", headers=headers)
    assert resp.status_code == 403
