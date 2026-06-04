"""Integration tests for app/modules/tenant/service.py."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.models import Abonnement, StatutAbonnement
from app.modules.tenant.schemas import (
    EstablishmentSettings,
    EstablishmentSettingsUpdateRequest,
    FeatureToggle,
    PlanLimits,
    SiteAffectationCreateRequest,
    TimeclockSettings,
)
from app.modules.tenant.service import (
    create_site_affectation,
    get_establishment_settings,
    get_plan_limits,
    organization_overview,
    update_establishment_settings,
)
from tests.integration.conftest import (
    make_base_seed,
    make_establishment,
    make_establishment_ctx,
    make_organisation,
    make_role,
    make_user,
)
from datetime import UTC, datetime


# ── EstablishmentSettings ─────────────────────────────────────────────────────


async def test_get_establishment_settings_defaults(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    settings = await get_establishment_settings(test_db, seed.ctx)
    assert settings.timeclock.enabled is True
    assert settings.cleaning.enabled is True


async def test_update_settings_partial_merge_preserves_other_fields(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    await update_establishment_settings(
        EstablishmentSettingsUpdateRequest(cleaning=FeatureToggle(enabled=False)),
        test_db,
        seed.ctx,
    )
    settings = await get_establishment_settings(test_db, seed.ctx)
    assert settings.cleaning.enabled is False
    assert settings.timeclock.enabled is True  # unchanged


async def test_update_settings_timeclock(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    await update_establishment_settings(
        EstablishmentSettingsUpdateRequest(timeclock=TimeclockSettings(enabled=False)),
        test_db,
        seed.ctx,
    )
    settings = await get_establishment_settings(test_db, seed.ctx)
    assert settings.timeclock.enabled is False


async def test_update_settings_non_org_admin_raises_403(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    non_admin_ctx = make_establishment_ctx(
        seed.org, seed.est, seed.manager, is_org_admin=False
    )
    with pytest.raises(HTTPException) as exc_info:
        await update_establishment_settings(
            EstablishmentSettingsUpdateRequest(cleaning=FeatureToggle(enabled=False)),
            test_db,
            non_admin_ctx,
        )
    assert exc_info.value.status_code == 403


# ── PlanLimits ────────────────────────────────────────────────────────────────


async def test_get_plan_limits_no_subscription_returns_defaults(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    limits = await get_plan_limits(test_db, seed.ctx)
    assert limits.max_establishments == 999
    assert limits.plan_name == "unlimited"


async def test_get_plan_limits_with_active_subscription(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    abonnement = Abonnement(
        organisation_id=seed.org.id,
        stripe_subscription_id="sub_test_123",
        stripe_price_id="price_test_abc",
        statut=StatutAbonnement.ACTIVE,
        intervalle="month",
        date_debut=datetime.now(UTC),
        features_limits={
            "max_establishments": 3,
            "max_operators_per_site": 10,
            "max_users_per_org": 5,
            "features_enabled": ["timeclock", "cleaning"],
            "plan_name": "starter",
        },
    )
    test_db.add(abonnement)
    await test_db.commit()

    limits = await get_plan_limits(test_db, seed.ctx)
    assert limits.max_establishments == 3
    assert limits.plan_name == "starter"


async def test_get_plan_limits_canceled_subscription_uses_defaults(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    abonnement = Abonnement(
        organisation_id=seed.org.id,
        stripe_subscription_id="sub_canceled_456",
        stripe_price_id="price_test_abc",
        statut=StatutAbonnement.CANCELED,  # not ACTIVE or TRIALING
        intervalle="month",
        date_debut=datetime.now(UTC),
        features_limits={"max_establishments": 1, "plan_name": "canceled"},
    )
    test_db.add(abonnement)
    await test_db.commit()

    limits = await get_plan_limits(test_db, seed.ctx)
    # Canceled subscription should be ignored → defaults
    assert limits.max_establishments == 999


# ── Site affectation upsert ───────────────────────────────────────────────────


async def test_create_site_affectation_upsert_updates_existing(test_db: AsyncSession):
    seed = await make_base_seed(test_db)

    # First call creates
    payload = SiteAffectationCreateRequest(
        utilisateur_id=seed.operator.id,
        role_id=seed.operator_role.id,
        is_active=True,
    )
    result1 = await create_site_affectation(seed.est.id, payload, test_db, seed.ctx)
    assert result1.is_active is True

    # Second call with same triple updates (upsert)
    payload_update = SiteAffectationCreateRequest(
        utilisateur_id=seed.operator.id,
        role_id=seed.operator_role.id,
        poste_principal="Chef de partie",
        is_active=True,
    )
    result2 = await create_site_affectation(seed.est.id, payload_update, test_db, seed.ctx)
    assert result2.poste_principal == "Chef de partie"


# ── Organisation overview ─────────────────────────────────────────────────────


async def test_organization_overview_returns_correct_structure(test_db: AsyncSession):
    seed = await make_base_seed(test_db)
    from app.core.dependencies import CurrentOrganisation

    org_ctx = CurrentOrganisation(
        organisation_id=seed.org.id,
        nom_entite=seed.org.nom_entite,
    )
    overview = await organization_overview(org_ctx, test_db)
    assert overview.organization_id == seed.org.id
    site_ids = {s.id for s in overview.establishments}
    assert seed.est.id in site_ids
