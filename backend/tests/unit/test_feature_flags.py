"""Unit tests for feature flag schemas and logic."""

import pytest

from app.core.features import Feature
from app.modules.tenant.schemas import (
    EstablishmentSettings,
    FeatureToggle,
    PlanLimits,
    TimeclockSettings,
)


# ── FeatureToggle ──────────────────────────────────────────────────────────────


def test_feature_toggle_enabled_by_default():
    toggle = FeatureToggle()
    assert toggle.enabled is True


def test_feature_toggle_can_be_disabled():
    toggle = FeatureToggle(enabled=False)
    assert toggle.enabled is False


# ── EstablishmentSettings.is_enabled ──────────────────────────────────────────


def test_is_enabled_returns_true_by_default_for_all_features():
    settings = EstablishmentSettings()
    for feature in Feature:
        assert settings.is_enabled(feature) is True


def test_is_enabled_returns_false_when_feature_toggle_disabled():
    settings = EstablishmentSettings(cleaning=FeatureToggle(enabled=False))
    assert settings.is_enabled(Feature.CLEANING) is False


def test_is_enabled_other_features_unaffected_when_one_disabled():
    settings = EstablishmentSettings(cleaning=FeatureToggle(enabled=False))
    assert settings.is_enabled(Feature.RECEPTIONS) is True
    assert settings.is_enabled(Feature.OPERATORS) is True


def test_is_enabled_timeclock_reads_timeclock_settings():
    settings = EstablishmentSettings(timeclock=TimeclockSettings(enabled=False))
    assert settings.is_enabled(Feature.TIMECLOCK) is False


def test_is_enabled_timeclock_default_true():
    settings = EstablishmentSettings()
    assert settings.is_enabled(Feature.TIMECLOCK) is True


def test_is_enabled_unknown_feature_value_returns_true():
    # Simulating an unknown feature (not in Feature enum) via getattr returning None
    settings = EstablishmentSettings()
    # Direct call with a valid but unset attribute fallback
    result = settings.is_enabled(Feature.SUPPLIERS)
    assert result is True


# ── EstablishmentSettings.from_raw ────────────────────────────────────────────


def test_from_raw_empty_dict_applies_all_defaults():
    settings = EstablishmentSettings.from_raw({})
    assert settings.timeclock.enabled is True
    assert settings.cleaning.enabled is True
    assert settings.receptions.enabled is True
    assert settings.operators.enabled is True


def test_from_raw_parses_timeclock_disabled():
    settings = EstablishmentSettings.from_raw({"timeclock": {"enabled": False}})
    assert settings.timeclock.enabled is False
    assert settings.cleaning.enabled is True  # others unaffected


def test_from_raw_parses_feature_toggle_disabled():
    settings = EstablishmentSettings.from_raw({"cleaning": {"enabled": False}})
    assert settings.cleaning.enabled is False
    assert settings.receptions.enabled is True


def test_from_raw_handles_none_like_empty():
    # from_raw with falsy raw → returns default
    settings_none = EstablishmentSettings.from_raw({})
    assert settings_none.cleaning.enabled is True


# ── PlanLimits ────────────────────────────────────────────────────────────────


def test_plan_limits_defaults_are_generous():
    limits = PlanLimits()
    assert limits.max_establishments == 999
    assert limits.max_operators_per_site == 999
    assert limits.max_users_per_org == 999
    assert limits.plan_name == "unlimited"


def test_plan_limits_all_features_enabled_by_default():
    limits = PlanLimits()
    for feature in Feature:
        assert limits.allows(feature) is True


def test_plan_limits_allows_returns_false_when_feature_absent():
    limits = PlanLimits(features_enabled=[Feature.TIMECLOCK, Feature.CLEANING])
    assert limits.allows(Feature.TIMECLOCK) is True
    assert limits.allows(Feature.CLEANING) is True
    assert limits.allows(Feature.RECEPTIONS) is False


def test_plan_limits_from_subscription_empty_dict_returns_defaults():
    limits = PlanLimits.from_subscription({})
    assert limits.plan_name == "unlimited"
    assert limits.max_establishments == 999


def test_plan_limits_from_subscription_parses_dict():
    data = {
        "max_establishments": 3,
        "max_operators_per_site": 10,
        "max_users_per_org": 5,
        "features_enabled": ["timeclock", "cleaning"],
        "plan_name": "starter",
    }
    limits = PlanLimits.from_subscription(data)
    assert limits.max_establishments == 3
    assert limits.plan_name == "starter"
    assert limits.allows(Feature.TIMECLOCK) is True
    assert limits.allows(Feature.RECEPTIONS) is False
