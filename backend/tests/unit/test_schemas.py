"""Unit tests for Pydantic schema validation."""

from datetime import UTC, date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.equipments.models import TypeEquipement
from app.modules.receptions.schemas import ReceptionItemCreate, ReceptionSessionCreate
from app.modules.tenant.schemas import (
    EstablishmentSettings,
    OrganisationCreateRequest,
    SiteEquipmentCreateRequest,
)

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
    settings = EstablishmentSettings.from_raw(
        {"timeclock": {"enabled": False, "applies_to_managers": True}}
    )
    dumped = settings.model_dump()
    restored = EstablishmentSettings.from_raw(dumped)
    assert restored.timeclock.enabled is False
    assert restored.timeclock.applies_to_managers is True
    assert restored.cleaning.enabled is True


# ── ReceptionSessionCreate ────────────────────────────────────────────────────


def test_reception_session_create_truck_condition_ok_defaults_to_true():
    from datetime import datetime

    req = ReceptionSessionCreate(supplier_id=uuid4(), received_at=datetime.now(UTC))
    assert req.truck_condition_ok is True


def test_reception_session_create_truck_condition_ok_false_accepted():
    from datetime import datetime

    req = ReceptionSessionCreate(
        supplier_id=uuid4(), received_at=datetime.now(UTC), truck_condition_ok=False
    )
    assert req.truck_condition_ok is False


# ── ReceptionItemCreate — validate_compliance ─────────────────────────────────


def _base_item(**overrides) -> dict:
    return {
        "product_id": uuid4(),
        "lot_number": "LOT-TEST",
        "dluo": date(2026, 12, 31),
        "is_compliant": True,
        **overrides,
    }


def test_reception_item_create_valid_compliant_good_packaging():
    item = ReceptionItemCreate(**_base_item(packaging_ok=True, is_compliant=True))
    assert item.is_compliant is True
    assert item.packaging_ok is True


def test_reception_item_create_valid_non_compliant_bad_packaging():
    item = ReceptionItemCreate(**_base_item(packaging_ok=False, is_compliant=False))
    assert item.is_compliant is False


def test_reception_item_create_packaging_ok_false_is_compliant_true_raises():
    """packaging_ok=False with is_compliant=True must be rejected by the validator."""
    with pytest.raises(ValidationError, match="emballage est non conforme"):
        ReceptionItemCreate(**_base_item(packaging_ok=False, is_compliant=True))


def test_reception_item_create_temperature_out_of_range_is_compliant_true_raises():
    """Temperature outside bounds with is_compliant=True must be rejected."""
    item_data = _base_item(
        measured_temperature=10.0,
        product_min_temp=0.0,
        product_max_temp=4.0,
        is_compliant=True,
    )
    with pytest.raises(ValidationError, match="température hors des limites"):
        ReceptionItemCreate(**item_data)


def test_reception_item_create_temperature_in_range_is_compliant_true_valid():
    item = ReceptionItemCreate(
        **_base_item(
            measured_temperature=2.5,
            product_min_temp=0.0,
            product_max_temp=4.0,
            is_compliant=True,
        )
    )
    assert item.is_compliant is True


def test_reception_item_create_temperature_out_of_range_is_compliant_false_valid():
    """Out-of-range temperature with is_compliant=False is a legitimate non-conformity."""
    item = ReceptionItemCreate(
        **_base_item(
            measured_temperature=8.0,
            product_min_temp=0.0,
            product_max_temp=4.0,
            is_compliant=False,
        )
    )
    assert item.is_compliant is False


def test_reception_item_create_no_temperature_thresholds_skips_temp_check():
    """When product_min/max_temp are None, temperature is not validated."""
    item = ReceptionItemCreate(
        **_base_item(
            measured_temperature=8.0,
            product_min_temp=None,
            product_max_temp=None,
            is_compliant=True,
        )
    )
    assert item.is_compliant is True


def test_reception_item_create_temperature_at_min_boundary_is_compliant():
    item = ReceptionItemCreate(
        **_base_item(
            measured_temperature=0.0,
            product_min_temp=0.0,
            product_max_temp=4.0,
            is_compliant=True,
        )
    )
    assert item.is_compliant is True


def test_reception_item_create_temperature_at_max_boundary_is_compliant():
    item = ReceptionItemCreate(
        **_base_item(
            measured_temperature=4.0,
            product_min_temp=0.0,
            product_max_temp=4.0,
            is_compliant=True,
        )
    )
    assert item.is_compliant is True


def test_reception_item_create_packaging_ok_defaults_to_true():
    item = ReceptionItemCreate(**_base_item())
    assert item.packaging_ok is True
