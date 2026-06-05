"""E2E tests for the Receptions domain."""

from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.catalog.models import Supplier, SupplierCountry, SupplierStatus
from app.modules.catalog.models import Product
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class ReceptionSeed:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    operator: Utilisateur
    manager_role: Role
    operator_role: Role
    supplier: Supplier
    product: Product


@pytest.fixture
async def seed_receptions(test_db: AsyncSession) -> ReceptionSeed:
    manager_email = "reception.manager@test.com"
    org = Organisation(
        nom_entite="Reception Test Org",
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=manager_email,
        admin_password_hash=get_password_hash("RecPass123!"),
    )
    test_db.add(org)
    await test_db.flush()

    est = Etablissement(organisation_id=org.id, nom_site="Reception Site", timezone="Europe/Paris")
    manager_role = Role(
        nom_role="MANAGER_REC",
        permissions={"manager": True, "can_manage_device_login": True},
    )
    operator_role = Role(nom_role="OPERATEUR_REC", permissions={})
    test_db.add_all([est, manager_role, operator_role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Rec",
        prenom="Manager",
        email=manager_email,
        mot_de_passe_hash=get_password_hash("RecPass123!"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Rec",
        prenom="Operator",
        email="reception.operator@test.com",
        mot_de_passe_hash=get_password_hash("RecOpPass123!"),
        code_pin=get_password_hash("3333"),
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

    supplier = Supplier(
        establishment_id=est.id,
        name="Fournisseur Réception",
        country=SupplierCountry.FRANCE,
        status=SupplierStatus.APPROVED,
    )
    test_db.add(supplier)
    await test_db.flush()

    product = Product(
        establishment_id=est.id,
        supplier_id=supplier.id,
        name="Produit Réception",
        has_temperature_control=False,
    )
    test_db.add(product)
    await test_db.commit()

    return ReceptionSeed(
        organisation=org,
        etablissement=est,
        manager=manager,
        operator=operator,
        manager_role=manager_role,
        operator_role=operator_role,
        supplier=supplier,
        product=product,
    )


async def _login(client: AsyncClient, seed: ReceptionSeed) -> str:
    resp = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "RecPass123!",
            "etablissement_id": str(seed.etablissement.id),
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_open_reception_session(client: AsyncClient, seed_receptions: ReceptionSeed):
    token = await _login(client, seed_receptions)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Device-Pin": "3333",
        "X-Operator-Id": str(seed_receptions.operator.id),
    }

    resp = await client.post(
        "/api/v1/reception-sessions",
        data={
            "supplier_id": str(seed_receptions.supplier.id),
            "received_at": "2024-06-01T10:00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["supplier_id"] == str(seed_receptions.supplier.id)
    assert data["status"].upper() == "OPEN"


async def test_add_reception_item(client: AsyncClient, seed_receptions: ReceptionSeed):
    token = await _login(client, seed_receptions)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Device-Pin": "3333",
        "X-Operator-Id": str(seed_receptions.operator.id),
    }

    session_resp = await client.post(
        "/api/v1/reception-sessions",
        data={
            "supplier_id": str(seed_receptions.supplier.id),
            "received_at": "2024-06-01T10:00:00",
        },
        headers=headers,
    )
    session_id = session_resp.json()["id"]

    item_resp = await client.post(
        f"/api/v1/reception-sessions/{session_id}/items",
        json={
            "product_id": str(seed_receptions.product.id),
            "lot_number": "LOT-E2E-001",
            "dluo": "2025-12-31",
            "is_compliant": True,
        },
        headers=headers,
    )
    assert item_resp.status_code == 201
    assert item_resp.json()["is_compliant"] is True


async def test_get_reception_session_detail(client: AsyncClient, seed_receptions: ReceptionSeed):
    token = await _login(client, seed_receptions)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Device-Pin": "3333",
        "X-Operator-Id": str(seed_receptions.operator.id),
    }

    session_resp = await client.post(
        "/api/v1/reception-sessions",
        data={
            "supplier_id": str(seed_receptions.supplier.id),
            "received_at": "2024-06-01T10:00:00",
        },
        headers=headers,
    )
    session_id = session_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/reception-sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id


async def test_close_reception_session(client: AsyncClient, seed_receptions: ReceptionSeed):
    token = await _login(client, seed_receptions)
    headers_with_pin = {
        "Authorization": f"Bearer {token}",
        "X-Device-Pin": "3333",
        "X-Operator-Id": str(seed_receptions.operator.id),
    }

    session_resp = await client.post(
        "/api/v1/reception-sessions",
        data={
            "supplier_id": str(seed_receptions.supplier.id),
            "received_at": "2024-06-01T10:00:00",
        },
        headers=headers_with_pin,
    )
    session_id = session_resp.json()["id"]

    close_resp = await client.patch(
        f"/api/v1/reception-sessions/{session_id}/close",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"].upper() == "CLOSED"
