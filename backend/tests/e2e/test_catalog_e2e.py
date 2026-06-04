"""E2E tests for the Catalog domain (suppliers and products)."""

from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class CatalogSeed:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    manager_role: Role


@pytest.fixture
async def seed_catalog(test_db: AsyncSession) -> CatalogSeed:
    manager_email = "catalog.manager@test.com"
    org = Organisation(
        nom_entite="Catalog Test Org",
        type_secteur=TypeSecteur.PRIVE,
        admin_login_email=manager_email,
        admin_password_hash=get_password_hash("CatalogPass123!"),
    )
    test_db.add(org)
    await test_db.flush()

    est = Etablissement(organisation_id=org.id, nom_site="Catalog Site", timezone="Europe/Paris")
    role = Role(nom_role="MANAGER_CAT", permissions={"manager": True, "can_manage_device_login": True})
    test_db.add_all([est, role])
    await test_db.flush()

    manager = Utilisateur(
        nom="Catalog", prenom="Manager",
        email=manager_email,
        mot_de_passe_hash=get_password_hash("CatalogPass123!"),
    )
    test_db.add(manager)
    await test_db.flush()
    test_db.add(AffectationSite(utilisateur_id=manager.id, etablissement_id=est.id, role_id=role.id))
    await test_db.commit()
    return CatalogSeed(organisation=org, etablissement=est, manager=manager, manager_role=role)


async def _login(client: AsyncClient, seed: CatalogSeed) -> str:
    resp = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed.manager.email,
            "password": "CatalogPass123!",
            "etablissement_id": str(seed.etablissement.id),
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── Supplier CRUD ─────────────────────────────────────────────────────────────


async def test_create_supplier(client: AsyncClient, seed_catalog: CatalogSeed):
    token = await _login(client, seed_catalog)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Boucherie Dupont", "country": "France", "status": "approved"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Boucherie Dupont"
    assert "id" in data


async def test_list_suppliers(client: AsyncClient, seed_catalog: CatalogSeed):
    token = await _login(client, seed_catalog)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/suppliers",
        json={"name": "Fournisseur List", "country": "France", "status": "approved"},
        headers=headers,
    )
    resp = await client.get("/api/v1/suppliers", headers=headers)
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()["items"]]
    assert "Fournisseur List" in names


async def test_update_supplier(client: AsyncClient, seed_catalog: CatalogSeed):
    token = await _login(client, seed_catalog)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Old Name", "country": "France", "status": "approved"},
        headers=headers,
    )
    supplier_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "New Name"


# ── Product CRUD ──────────────────────────────────────────────────────────────


async def test_create_product(client: AsyncClient, seed_catalog: CatalogSeed):
    token = await _login(client, seed_catalog)
    headers = {"Authorization": f"Bearer {token}"}

    # Create supplier first
    supplier_resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Produit Fournisseur", "country": "France", "status": "approved"},
        headers=headers,
    )
    supplier_id = supplier_resp.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Bœuf haché 5%",
            "supplier_id": supplier_id,
            "has_temperature_control": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Bœuf haché 5%"


async def test_delete_product(client: AsyncClient, seed_catalog: CatalogSeed):
    token = await _login(client, seed_catalog)
    headers = {"Authorization": f"Bearer {token}"}

    supplier_resp = await client.post(
        "/api/v1/suppliers",
        json={"name": "Delete Supplier", "country": "France", "status": "approved"},
        headers=headers,
    )
    supplier_id = supplier_resp.json()["id"]

    product_resp = await client.post(
        "/api/v1/products",
        json={"name": "Produit à supprimer", "supplier_id": supplier_id, "has_temperature_control": False},
        headers=headers,
    )
    product_id = product_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert delete_resp.status_code == 204
