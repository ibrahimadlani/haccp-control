"""
FastAPI router for the Tenant domain (organisations and establishments).

Exposes endpoints for:

- Organisation subscription listing.
- Establishment creation within an organisation.
- Organisation supervision overview.
- Establishment user and assignment management.
- Establishment soft/hard delete.
- Establishment feature-flag settings read/update.
- Platform-admin-only organisation creation.

All write operations that affect organisations or cross-establishment data
are gated by the establishment JWT (``CurrentSite``) or the organisation JWT
(``CurrentOrg``).  Organisation creation additionally requires the
``X-Platform-Admin-Key`` header.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentOrg, CurrentSite, DatabaseSession
from app.core.dependencies import require_platform_admin_key
from app.modules.tenant import service
from app.modules.tenant.schemas import (
    AbonnementListResponse,
    EstablishmentCreateRequest,
    EstablishmentResponse,
    EstablishmentSettings,
    EstablishmentSettingsUpdateRequest,
    OrganisationCreateRequest,
    OrganisationResponse,
    OrganizationOverviewResponse,
    PlanLimits,
    SiteAffectationCreateRequest,
    SiteAffectationResponse,
    SiteUserListResponse,
)

router = APIRouter(tags=["Organisation"])


@router.get("/organisations/{organisation_id}/subscriptions", response_model=AbonnementListResponse)
async def list_organization_subscriptions(
    organisation_id: UUID, db: DatabaseSession, current_org: CurrentOrg
) -> AbonnementListResponse:
    """List all Stripe subscriptions for an organisation.

    Args:
        organisation_id (UUID): Must match the JWT to prevent cross-org access.
        db (DatabaseSession): Injected async database session.
        current_org (CurrentOrg): The authenticated organisation context.

    Returns:
        AbonnementListResponse: Subscriptions ordered by start date descending.

    Raises:
        HTTPException: 403 Forbidden if ``organisation_id`` does not match the JWT.
    """
    return await service.list_organization_subscriptions(organisation_id, db, current_org)


@router.post(
    "/organisations/{organisation_id}/establishments",
    response_model=EstablishmentResponse,
    status_code=201,
)
async def create_organization_establishment(
    organisation_id: UUID,
    payload: EstablishmentCreateRequest,
    db: DatabaseSession,
    current_org: CurrentOrg,
) -> EstablishmentResponse:
    """Create a new establishment under an organisation.

    Args:
        organisation_id (UUID): Target organisation. Must match the JWT.
        payload (EstablishmentCreateRequest): Validated establishment data.
        db (DatabaseSession): Injected async database session.
        current_org (CurrentOrg): The authenticated organisation context.

    Returns:
        EstablishmentResponse: The created establishment.

    Raises:
        HTTPException: 403 Forbidden if the JWT organisation does not match.
        HTTPException: 409 Conflict if the SIRET is already in use.
    """
    return await service.create_organization_establishment(
        organisation_id, payload, db, current_org
    )


@router.get(
    "/organisations/{organisation_id}/overview", response_model=OrganizationOverviewResponse
)
async def read_organization_overview(
    organisation_id: UUID, organisation: CurrentOrg, db: DatabaseSession
) -> OrganizationOverviewResponse:
    """Return the organisation supervision dashboard payload.

    Args:
        organisation_id (UUID): Must match the JWT.
        organisation (CurrentOrg): The authenticated organisation context.
        db (DatabaseSession): Injected async database session.

    Returns:
        OrganizationOverviewResponse: Establishments, managers, and employees.

    Raises:
        HTTPException: 403 Forbidden if ``organisation_id`` does not match the JWT.
    """
    if organisation_id != organisation.organisation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden organisation scope."
        )
    return await service.organization_overview(organisation, db)


@router.get(
    "/establishments/{etablissement_id}/users/assigned", response_model=SiteUserListResponse
)
async def list_establishment_assigned_users(
    etablissement_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> SiteUserListResponse:
    """List all users assigned to a specific establishment.

    Args:
        etablissement_id (UUID): Target establishment primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SiteUserListResponse: User–role–assignment records.
    """
    return await service.list_site_users(etablissement_id, db, establishment)


@router.post(
    "/establishments/{etablissement_id}/assignments",
    response_model=SiteAffectationResponse,
    status_code=201,
)
async def create_establishment_assignment(
    etablissement_id: UUID,
    payload: SiteAffectationCreateRequest,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> SiteAffectationResponse:
    """Assign (or upsert) a user to an establishment with a specific role.

    Args:
        etablissement_id (UUID): Target establishment primary key.
        payload (SiteAffectationCreateRequest): User, role, and activation state.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SiteAffectationResponse: The created or updated assignment.
    """
    return await service.create_site_affectation(etablissement_id, payload, db, establishment)


@router.delete("/establishments/{etablissement_id}", status_code=204)
async def delete_establishment(
    etablissement_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    hard_delete: bool = Query(default=False),
) -> None:
    """Delete an establishment (soft by default, hard for platform admins).

    Args:
        etablissement_id (UUID): Target establishment primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        hard_delete (bool): When ``True``, perform a physical delete. Requires
            platform-admin rights.

    Raises:
        HTTPException: 400 if deleting the currently authenticated establishment.
        HTTPException: 403 Forbidden if insufficient rights.
    """
    return await service.delete_establishment(
        etablissement_id, db, establishment, hard_delete=hard_delete
    )


@router.get("/establishment-settings", response_model=EstablishmentSettings)
async def get_establishment_settings(
    db: DatabaseSession, establishment: CurrentSite
) -> EstablishmentSettings:
    """Return feature-flag settings for the locked establishment.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        EstablishmentSettings: Current settings with defaults applied.
    """
    return await service.get_establishment_settings(db, establishment)


@router.patch("/establishment-settings", response_model=EstablishmentSettings)
async def update_establishment_settings(
    payload: EstablishmentSettingsUpdateRequest, db: DatabaseSession, establishment: CurrentSite
) -> EstablishmentSettings:
    """Partially update feature-flag settings for the locked establishment.

    Only the organisation admin may call this endpoint.

    Args:
        payload (EstablishmentSettingsUpdateRequest): Sub-models to merge.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        EstablishmentSettings: The merged settings after the update.

    Raises:
        HTTPException: 403 Forbidden if the caller is not the org admin.
    """
    return await service.update_establishment_settings(payload, db, establishment)


@router.get("/plan-limits", response_model=PlanLimits)
async def get_plan_limits(db: DatabaseSession, establishment: CurrentSite) -> PlanLimits:
    """Return the feature limits granted by the organisation's active subscription.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        PlanLimits: Plan limits with generous defaults when no subscription exists.
    """
    return await service.get_plan_limits(db, establishment)


@router.post(
    "/organisations",
    response_model=OrganisationResponse,
    status_code=201,
    dependencies=[Depends(require_platform_admin_key)],
)
async def create_organization(
    payload: OrganisationCreateRequest, db: DatabaseSession
) -> OrganisationResponse:
    """Create a new organisation tenant (platform admin only).

    Requires the ``X-Platform-Admin-Key`` header to be present and valid.

    Args:
        payload (OrganisationCreateRequest): Organisation data including
            plain-text admin password.
        db (DatabaseSession): Injected async database session.

    Returns:
        OrganisationResponse: The created organisation (password hash excluded).

    Raises:
        HTTPException: 401 Unauthorized if the admin key is missing or invalid.
        HTTPException: 409 Conflict if the admin email is already in use.
    """
    return await service.create_organization(payload, db)
