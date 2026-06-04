from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.equipments.models import Equipement
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation, TypeSecteur


@dataclass(frozen=True)
class SeedData:
    organisation: Organisation
    etablissement: Etablissement
    manager: Utilisateur
    operator: Utilisateur
    equipement: Equipement


@pytest.fixture(scope="function")
async def seed_haccp_data(test_db: AsyncSession) -> SeedData:
    organisation = Organisation(
        nom_entite="Cuisine Centrale Test",
        type_secteur=TypeSecteur.PRIVE,
        identifiant_legal="TEST-ORG-001",
        admin_login_email="owner@test-org.com",
        admin_password_hash=get_password_hash("OrgOwnerPass123"),
    )
    test_db.add(organisation)
    await test_db.flush()

    etablissement = Etablissement(
        organisation_id=organisation.id,
        nom_site="Cuisine Paris 01",
        timezone="Europe/Paris",
    )
    manager_role = Role(
        nom_role="MANAGER",
        permissions={"can_manage_device_login": True},
    )
    operator_role = Role(
        nom_role="OPERATEUR",
        permissions={"can_create_temperature_record": True},
    )
    manager = Utilisateur(
        nom="Martin",
        prenom="Alice",
        email="manager@example.com",
        mot_de_passe_hash=get_password_hash("ValidPassword123"),
        code_pin=get_password_hash("1111"),
    )
    operator = Utilisateur(
        nom="Durand",
        prenom="Karim",
        email="operator@example.com",
        mot_de_passe_hash=get_password_hash("AnotherPassword123"),
        code_pin=get_password_hash("1234"),
    )
    test_db.add_all([etablissement, manager_role, operator_role, manager, operator])
    await test_db.flush()

    test_db.add_all(
        [
            AffectationSite(
                utilisateur_id=manager.id,
                etablissement_id=etablissement.id,
                role_id=manager_role.id,
                is_active=True,
            ),
            AffectationSite(
                utilisateur_id=operator.id,
                etablissement_id=etablissement.id,
                role_id=operator_role.id,
                is_active=True,
            ),
        ]
    )

    equipement = Equipement(
        etablissement_id=etablissement.id,
        nom="Chambre froide positive",
        temperature_min_cible=Decimal("0.00"),
        temperature_max_cible=Decimal("4.00"),
    )
    test_db.add(equipement)
    await test_db.commit()

    return SeedData(
        organisation=organisation,
        etablissement=etablissement,
        manager=manager,
        operator=operator,
        equipement=equipement,
    )


@pytest.mark.asyncio
async def test_manager_login_valid_and_invalid_credentials(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    invalid_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "WrongPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert invalid_response.status_code == 401
    assert invalid_response.json()["detail"] == "Invalid manager credentials."

    valid_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert valid_response.status_code == 200

    payload = valid_response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["establishment"]["etablissement_id"] == str(seed_haccp_data.etablissement.id)
    assert payload["establishment"]["nom_site"] == seed_haccp_data.etablissement.nom_site


@pytest.mark.asyncio
async def test_public_establishment_metadata_endpoint(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    response = await client.get(f"/api/v1/establishments/{seed_haccp_data.etablissement.id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["etablissement_id"] == str(seed_haccp_data.etablissement.id)
    assert payload["nom_site"] == seed_haccp_data.etablissement.nom_site
    assert payload["timezone"] == seed_haccp_data.etablissement.timezone


@pytest.mark.asyncio
async def test_two_level_auth_rejects_invalid_operator_pin(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/operator-sessions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "9999",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid operator credentials."


@pytest.mark.asyncio
async def test_two_level_auth_authenticates_operator_from_pin_only(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/operator-sessions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert response.status_code == 200
    assert response.json()["operator"]["email"] == seed_haccp_data.operator.email


@pytest.mark.asyncio
async def test_two_level_auth_rejects_manager_pin_on_operator_flow(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/operator-sessions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1111",
            "X-Operator-Id": str(seed_haccp_data.manager.id),
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid operator credentials."


@pytest.mark.asyncio
async def test_two_level_auth_resolves_duplicate_pins_with_explicit_operator_id(
    client: AsyncClient,
    test_db: AsyncSession,
    seed_haccp_data: SeedData,
) -> None:
    second_operator = Utilisateur(
        nom="Lopez",
        prenom="Mina",
        email="operator.duplicate@example.com",
        mot_de_passe_hash=get_password_hash("DuplicateOperatorPass123"),
        code_pin=get_password_hash("1234"),
    )
    test_db.add(second_operator)
    await test_db.flush()

    operator_role_result = await test_db.execute(select(Role).where(Role.nom_role == "OPERATEUR"))
    operator_role = operator_role_result.scalar_one()

    test_db.add(
        AffectationSite(
            utilisateur_id=second_operator.id,
            etablissement_id=seed_haccp_data.etablissement.id,
            role_id=operator_role.id,
            is_active=True,
        )
    )
    await test_db.commit()

    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    first_operator_response = await client.post(
        "/api/v1/operator-sessions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert first_operator_response.status_code == 200
    assert first_operator_response.json()["operator"]["email"] == seed_haccp_data.operator.email

    second_operator_response = await client.post(
        "/api/v1/operator-sessions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(second_operator.id),
        },
    )
    assert second_operator_response.status_code == 200
    assert second_operator_response.json()["operator"]["email"] == second_operator.email


@pytest.mark.asyncio
async def test_auth_operators_lists_active_site_collaborators(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = await client.get(
        f"/api/v1/establishments/{seed_haccp_data.etablissement.id}/users?role=SITE_EMPLOYEE",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 2

    manager_row = next(
        (item for item in payload if item["email"] == seed_haccp_data.manager.email),
        None,
    )
    operator_row = next(
        (item for item in payload if item["email"] == seed_haccp_data.operator.email),
        None,
    )

    assert manager_row is not None
    assert operator_row is not None
    assert manager_row["is_active"] is True
    assert operator_row["is_active"] is True


@pytest.mark.asyncio
async def test_haccp_equipment_listing_requires_operator_session_and_returns_site_equipment(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    manager_mode = await client.get(
        "/api/v1/equipments",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert manager_mode.status_code == 200
    assert isinstance(manager_mode.json().get("items"), list)

    response = await client.get(
        "/api/v1/equipments",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == str(seed_haccp_data.equipement.id)
    assert payload["items"][0]["name"] == seed_haccp_data.equipement.nom


@pytest.mark.asyncio
async def test_operator_mode_equipment_listing_requires_both_headers(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    missing_operator_id = await client.get(
        "/api/v1/equipments",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
        },
    )
    assert missing_operator_id.status_code == 401
    assert "both X-Device-Pin and X-Operator-Id" in missing_operator_id.json()["detail"]

    missing_pin = await client.get(
        "/api/v1/equipments",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert missing_pin.status_code == 401
    assert "both X-Device-Pin and X-Operator-Id" in missing_pin.json()["detail"]


@pytest.mark.asyncio
async def test_organisation_login_valid_and_invalid_credentials(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    invalid_response = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": "owner@test-org.com",
            "password": "WrongOrgPassword123",
        },
    )
    assert invalid_response.status_code == 401
    assert invalid_response.json()["detail"] == "Invalid organisation credentials."

    valid_response = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": "owner@test-org.com",
            "password": "OrgOwnerPass123",
        },
    )
    assert valid_response.status_code == 200

    payload = valid_response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["organisation"]["organisation_id"] == str(seed_haccp_data.organisation.id)
    assert payload["organisation"]["nom_entite"] == seed_haccp_data.organisation.nom_entite


@pytest.mark.asyncio
async def test_organisation_overview_requires_valid_organisation_token(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    unauthorized = await client.get(
        f"/api/v1/organisations/{seed_haccp_data.organisation.id}/overview"
    )
    assert unauthorized.status_code == 401

    login_response = await client.post(
        "/api/v1/organisation-sessions",
        json={
            "email": "owner@test-org.com",
            "password": "OrgOwnerPass123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = await client.get(
        f"/api/v1/organisations/{seed_haccp_data.organisation.id}/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    payload = response.json()

    # Contract compatibility: API keeps legacy French keys while internals use English symbols.
    assert payload["organisation_id"] == str(seed_haccp_data.organisation.id)
    assert payload["nom_entite"] == seed_haccp_data.organisation.nom_entite
    assert len(payload["etablissements"]) == 1
    assert "employees" not in payload
    assert "employes" in payload

    manager_row = next(
        (item for item in payload["managers"] if item["email"] == seed_haccp_data.manager.email),
        None,
    )
    employee_row = next(
        (item for item in payload["employes"] if item["email"] == seed_haccp_data.operator.email),
        None,
    )
    assert manager_row is not None
    assert employee_row is not None


@pytest.mark.asyncio
async def test_haccp_non_compliant_temperature_requires_corrective_action(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/temperature-records",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        json={
            "equipment_id": str(seed_haccp_data.equipement.id),
            "measured_value": "14.00",
            "source": "MANUEL",
        },
    )
    assert response.status_code == 201

    payload = response.json()
    assert payload["equipment_id"] == str(seed_haccp_data.equipement.id)
    assert payload["measured_value"] == "14.00"
    assert payload["temperature_min_cible"] == "0.00"
    assert payload["temperature_max_cible"] == "4.00"
    assert payload["is_conforme"] is False
    assert payload["action_corrective_required"] is True


@pytest.mark.asyncio
async def test_haccp_non_compliant_temperature_requires_meaningful_corrective_comment(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    record_response = await client.post(
        "/api/v1/temperature-records",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        json={
            "equipment_id": str(seed_haccp_data.equipement.id),
            "measured_value": "14.00",
            "source": "MANUEL",
        },
    )
    assert record_response.status_code == 201
    record_payload = record_response.json()
    nc_id = record_payload["nonconformity_id"]
    assert nc_id is not None

    # Acknowledge the NC (OPEN → IN_PROGRESS) before submitting a corrective action.
    ack_response = await client.patch(
        f"/api/v1/nonconformities/{nc_id}/acknowledge",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )
    assert ack_response.status_code == 200

    blank_comment_response = await client.post(
        f"/api/v1/nonconformities/{nc_id}/corrective-action",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        data={"description": "   "},
    )
    assert blank_comment_response.status_code == 422
    assert blank_comment_response.json()["detail"] == "Corrective action description is required."


@pytest.mark.asyncio
async def test_haccp_corrective_action_uploads_optional_photo_to_s3(
    client: AsyncClient,
    seed_haccp_data: SeedData,
) -> None:
    login_response = await client.post(
        "/api/v1/establishment-sessions",
        json={
            "email": seed_haccp_data.manager.email,
            "password": "ValidPassword123",
            "etablissement_id": str(seed_haccp_data.etablissement.id),
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    non_compliant_record_response = await client.post(
        "/api/v1/temperature-records",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        json={
            "equipment_id": str(seed_haccp_data.equipement.id),
            "measured_value": "14.00",
            "source": "MANUEL",
        },
    )
    assert non_compliant_record_response.status_code == 201
    first_record = non_compliant_record_response.json()
    record_id = first_record["id"]
    nc_id = first_record["nonconformity_id"]
    assert nc_id is not None

    # Acknowledge (OPEN → IN_PROGRESS) before submitting corrective action.
    await client.patch(
        f"/api/v1/nonconformities/{nc_id}/acknowledge",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )

    response = await client.post(
        f"/api/v1/nonconformities/{nc_id}/corrective-action",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        data={"description": "Produit isolé, maintenance prévenue et frigo recontrôlé."},
        files={"photo": ("corrective-action.png", b"fake-image-bytes", "image/png")},
    )
    assert response.status_code == 201

    payload = response.json()
    assert payload["releve_id"] == record_id
    assert payload["description"] == "Produit isolé, maintenance prévenue et frigo recontrôlé."
    assert payload["photo_s3_key"] == "tests/mock-upload.png"
    assert payload["photo_url"] == "http://test-s3.local/tests/mock-upload.png"

    second_record_response = await client.post(
        "/api/v1/temperature-records",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        json={
            "equipment_id": str(seed_haccp_data.equipement.id),
            "measured_value": "14.00",
            "source": "MANUEL",
        },
    )
    assert second_record_response.status_code == 201
    second_record = second_record_response.json()
    second_record_id = second_record["id"]
    second_nc_id = second_record["nonconformity_id"]

    await client.patch(
        f"/api/v1/nonconformities/{second_nc_id}/acknowledge",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
    )

    response_without_photo = await client.post(
        f"/api/v1/nonconformities/{second_nc_id}/corrective-action",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Device-Pin": "1234",
            "X-Operator-Id": str(seed_haccp_data.operator.id),
        },
        data={"description": "Produit isolé sans prise de photo."},
    )
    assert response_without_photo.status_code == 201
    payload_without_photo = response_without_photo.json()
    assert payload_without_photo["releve_id"] == second_record_id
    assert payload_without_photo["photo_s3_key"] is None
    assert payload_without_photo["photo_url"] is None
