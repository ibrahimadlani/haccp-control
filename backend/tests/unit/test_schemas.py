"""Unit tests for Pydantic schema validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.tenant.schemas import (
    EstablishmentSettings,
    OrganisationCreateRequest,
    SiteEquipmentCreateRequest,
)
from app.modules.equipments.models import TypeEquipement


# ── SiteEquipmentCreateRequest ────────────────────────────────────────────────


def test_equipment_create_valid_temperature_range():
    req = SiteEquipmentCreateRequest(
        name="Chambre froide",
        equipment_type=TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
        min_target_temperature=Decimal("0.00"),
        max_target_temperature=Decimal("4.00"),
    )
    assert req.min_target_temperature == Decimal("0.00")
    assert req.max_target_temperature == Decimal("4.00")


def test_equipment_create_min_equals_max_raises():
    with pytest.raises(ValidationError, match="min_target_temperature must be strictly lower"):
        SiteEquipmentCreateRequest(
            name="Frigo",
            equipment_type=TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
            min_target_temperature=Decimal("4.00"),
            max_target_temperature=Decimal("4.00"),
        )


def test_equipment_create_min_greater_than_max_raises():
    with pytest.raises(ValidationError):
        SiteEquipmentCreateRequest(
            name="Frigo",
            equipment_type=TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
            min_target_temperature=Decimal("5.00"),
            max_target_temperature=Decimal("4.00"),
        )


def test_equipment_create_coerces_float_to_decimal():
    req = SiteEquipmentCreateRequest(
        name="Frigo",
        equipment_type=TypeEquipement.CHAMBRE_FROIDE_POSITIVE,
        min_target_temperature=0,  # int coerced
        max_target_temperature=4,
    )
    assert req.min_target_temperature == Decimal("0")


def test_equipment_create_negative_temperatures_valid():
    req = SiteEquipmentCreateRequest(
        name="Surgélateur",
        equipment_type=TypeEquipement.CHAMBRE_FROIDE_NEGATIVE,
        min_target_temperature=Decimal("-25.00"),
        max_target_temperature=Decimal("-18.00"),
    )
    assert req.min_target_temperature < req.max_target_temperature


# ── OrganisationCreateRequest ─────────────────────────────────────────────────


def test_organisation_create_short_password_raises():
    with pytest.raises(ValidationError):
        OrganisationCreateRequest(
            nom_entite="Ma Boucherie",
            type_secteur="PRIVE",
            admin_login_email="admin@example.com",
            admin_password="short",  # < 12 chars
        )


def test_organisation_create_valid():
    req = OrganisationCreateRequest(
        nom_entite="Ma Boucherie",
        type_secteur="PRIVE",
        admin_login_email="admin@example.com",
        admin_password="secure_password_123",
    )
    assert req.nom_entite == "Ma Boucherie"


def test_organisation_create_password_exactly_12_chars_valid():
    req = OrganisationCreateRequest(
        nom_entite="Ma Boucherie",
        type_secteur="PRIVE",
        admin_login_email="admin@example.com",
        admin_password="a" * 12,
    )
    assert len(req.admin_password) == 12


# ── EstablishmentSettings ─────────────────────────────────────────────────────


def test_establishment_settings_model_dump_round_trip():
    settings = EstablishmentSettings.from_raw({"timeclock": {"enabled": False, "applies_to_managers": True}})
    dumped = settings.model_dump()
    restored = EstablishmentSettings.from_raw(dumped)
    assert restored.timeclock.enabled is False
    assert restored.timeclock.applies_to_managers is True
    assert restored.cleaning.enabled is True
