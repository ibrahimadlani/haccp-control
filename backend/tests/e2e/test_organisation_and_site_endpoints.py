from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.equipments.models import Equipement
from app.modules.tenant.models import Abonnement, Etablissement, Organisation, StatutAbonnement, TypeSecteur


@dataclass(frozen=True)
class OrganisationAdminSeed:
    organisation: Organisation
    establishment: Etablissement
    manager: Utilisateur
    manager_role: Role
    operator: Utilisateur
    operator_role: Role
    equipment: Equipement
    abonnement: Abonnement


@pytest.fixture(scope="function")
async def seed_organisation_admin_data(test_db: AsyncSession) -> OrganisationAdminSeed:
    organisation = Organisation(
        nom_entite="Organisation Admin Test",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="ORG-ADMIN-001",
        admin_login_email="owner.org-admin@test.com",
        admin_password_hash=get_password_hash("OrgOwnerPass123!"),
    )
    test_db.add(organisation)
    await test_db.flush()

    establishment = Etablissement(
        organisation_id=organisation.id,
        nom_site="Site principal admin",
        timezone="Europe/Paris",
    )
    manager_role = Role(
        nom_role="MANAGER",
        permissions={"manager": True, "can_manage_device_login": True},
    )
    operator_role = Role(
        nom_role="OPERATEUR",
        permissions={"can_create_temperature_record": True},
    )
    manager = Utilisateur(
        nom="Manager",
        prenom="Olivia",
        email="manager.org-admin@test.com",
        mot_de_passe_hash=get_password_hash("ValidPassword123"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Employe",
        prenom="Nina",
        email="operator.org-admin@test.com",
        mot_de_passe_hash=get_password_hash("AnotherPassword123"),
        code_pin=get_password_hash("1234"),
    )
    test_db.add_all([establishment, manager_role, operator_role, manager, operator])
    await test_db.flush()

    test_db.add_all(
        [
            AffectationSite(
                utilisateur_id=manager.id,
                etablissement_id=establishment.id,
                role_id=manager_role.id,
                is_active=True,
            ),
            AffectationSite(
                utilisateur_id=operator.id,
                etablissement_id=establishment.id,
                role_id=operator_role.id,
                is_active=True,
            ),
        ]
    )

    equipment = Equipement(
        etablissement_id=establishment.id,
        nom="Frigo principal",
        temperature_min_cible=Decimal("0.00"),
        temperature_max_cible=Decimal("4.00"),
    )
    abonnement = Abonnement(
        organisation_id=organisation.id,
        stripe_subscription_id="sub_test_org_admin_001",
        stripe_price_id="price_test_org_admin_001",
        statut=StatutAbonnement.ACTIVE,
        intervalle="month",
        date_debut=datetime.now(UTC),
        date_fin_periode=None,
    )
    test_db.add_all([equipment, abonnement])
    await test_db.commit()

    return OrganisationAdminSeed(
        organisation=organisation,
        establishment=establishment,
        manager=manager,
        manager_role=manager_role,
        operator=operator,
        operator_role=operator_role,
        equipment=equipment,
        abonnement=abonnement,
    )


@pytest.mark.asyncio
async def test_create_organisation_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/organisations",
        json={
            "nom_entite": "Nouvelle Organisation SaaS",
            "type_secteur": "PRIVE",
            "identifiant_legal": "NEW-ORG-001",
            "admin_login_email": "owner.new-org@test.com",
            "admin_password": "StrongOwnerPass123!",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["nom_entite"] == "Nouvelle Organisation SaaS"
    assert payload["admin_login_email"] == "owner.new-org@test.com"


@pytest.mark.asyncio
async def test_get_organisation_abonnements_endpoint(
    client: AsyncClient,
    seed_organisation_admin_data: OrganisationAdminSeed,
) -> None:
    login = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": seed_organisation_admin_data.organisation.admin_login_email,
            "password": "OrgOwnerPass123!",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = await client.get(
        f"/api/v1/organisations/{seed_organisation_admin_data.organisation.id}/subscriptions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["stripe_subscription_id"] == "sub_test_org_admin_001"


@pytest.mark.asyncio
async def test_create_establishment_under_organisation_endpoint(
    client: AsyncClient,
    seed_organisation_admin_data: OrganisationAdminSeed,
) -> None:
    login = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": seed_organisation_admin_data.organisation.admin_login_email,
            "password": "OrgOwnerPass123!",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = await client.post(
        f"/api/v1/organisations/{seed_organisation_admin_data.organisation.id}/establishments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nom_site": "Nouveau labo cuisine",
            "adresse": "10 rue des tests",
            "siret": "99887766554433",
            "type_activite": "Labo",
            "timezone": "Europe/Paris",
            "telephone_site": "+33199999999",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["nom_site"] == "Nouveau labo cuisine"
    assert payload["organisation_id"] == str(seed_organisation_admin_data.organisation.id)


@pytest.mark.asyncio
async def test_organization_scope_isolation_on_subscriptions_and_establishments(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_organisation_admin_data: OrganisationAdminSeed,
) -> None:
    other_org = Organisation(
        nom_entite="Organisation Externe",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="ORG-ADMIN-EXT-001",
        admin_login_email="owner.external@test.com",
        admin_password_hash=get_password_hash("ExternalOwnerPass123!"),
    )
    test_db.add(other_org)
    await test_db.commit()
    await test_db.refresh(other_org)

    login = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": seed_organisation_admin_data.organisation.admin_login_email,
            "password": "OrgOwnerPass123!",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    subscriptions = await client.get(
        f"/api/v1/organisations/{other_org.id}/subscriptions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert subscriptions.status_code == 403
    assert subscriptions.json()["detail"] == "Forbidden organisation scope."

    create_establishment = await client.post(
        f"/api/v1/organisations/{other_org.id}/establishments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nom_site": "Tentative Hors Scope",
            "adresse": "10 rue Scope",
            "siret": "11223344556677",
            "type_activite": "Cuisine",
            "timezone": "Europe/Paris",
            "telephone_site": "+33111111111",
        },
    )
    assert create_establishment.status_code == 403
    assert create_establishment.json()["detail"] == "Forbidden organisation scope."


@pytest.mark.asyncio
async def test_site_equipment_list_and_create_endpoints(
    client: AsyncClient,
    seed_organisation_admin_data: OrganisationAdminSeed,
) -> None:
    login = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_organisation_admin_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_organisation_admin_data.establishment.id),
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    list_response = await client.get(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}/equipments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    create_response = await client.post(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}/equipments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Congelateur zone 2",
            "equipment_type": "CONGELATEUR_CONSERVATEUR",
            "min_target_temperature": "-22.00",
            "max_target_temperature": "-18.00",
        },
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["name"] == "Congelateur zone 2"


@pytest.mark.asyncio
async def test_site_users_and_affectations_endpoints(
    client: AsyncClient,
    seed_organisation_admin_data: OrganisationAdminSeed,
    test_db: AsyncSession,
) -> None:
    login = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_organisation_admin_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_organisation_admin_data.establishment.id),
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    users_response = await client.get(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert users_response.status_code == 200
    assert len(users_response.json()) >= 2

    new_user = Utilisateur(
        nom="Nouveau",
        prenom="Profil",
        email="new.profile@test.com",
        mot_de_passe_hash=get_password_hash("BrandNewPass123!"),
        code_pin=get_password_hash("5555"),
    )
    test_db.add(new_user)
    await test_db.flush()

    affect_response = await client.post(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}/assignments",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "utilisateur_id": str(new_user.id),
            "role_id": str(seed_organisation_admin_data.operator_role.id),
            "poste_principal": "Commis",
            "is_active": True,
        },
    )
    assert affect_response.status_code == 201
    affect_payload = affect_response.json()
    assert affect_payload["utilisateur_id"] == str(new_user.id)
    assert affect_payload["role_id"] == str(seed_organisation_admin_data.operator_role.id)


@pytest.mark.asyncio
async def test_delete_establishment_soft_and_hard_requires_platform_admin(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_organisation_admin_data: OrganisationAdminSeed,
) -> None:
    secondary_establishment = Etablissement(
        organisation_id=seed_organisation_admin_data.organisation.id,
        nom_site="Site secondaire admin",
        timezone="Europe/Paris",
    )
    test_db.add(secondary_establishment)
    await test_db.flush()

    test_db.add(
        AffectationSite(
            utilisateur_id=seed_organisation_admin_data.manager.id,
            etablissement_id=secondary_establishment.id,
            role_id=seed_organisation_admin_data.manager_role.id,
            is_active=True,
        )
    )
    await test_db.commit()

    login = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_organisation_admin_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(secondary_establishment.id),
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    soft_delete = await client.delete(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert soft_delete.status_code == 204

    establishment_result = await test_db.execute(
        select(Etablissement).where(
            Etablissement.id == seed_organisation_admin_data.establishment.id
        )
    )
    establishment = establishment_result.scalar_one()
    assert establishment.deleted_at is not None

    forbidden_hard_delete = await client.delete(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden_hard_delete.status_code == 403
    assert (
        forbidden_hard_delete.json()["detail"]
        == "Hard delete is restricted to platform administrators."
    )

    seed_organisation_admin_data.manager_role.permissions = {
        "manager": True,
        "can_manage_device_login": True,
        "platform_admin": True,
    }
    await test_db.commit()

    allowed_hard_delete = await client.delete(
        f"/api/v1/establishments/{seed_organisation_admin_data.establishment.id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert allowed_hard_delete.status_code == 204

    deleted_establishment_result = await test_db.execute(
        select(Etablissement).where(
            Etablissement.id == seed_organisation_admin_data.establishment.id
        )
    )
    assert deleted_establishment_result.scalar_one_or_none() is None
