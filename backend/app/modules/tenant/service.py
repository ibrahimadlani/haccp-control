"""
Business logic for the Tenant domain.

Provides service functions for the two main tenant management workflows:

1. **Organisation management** — creating organisations and listing their
   subscriptions.  Organisation creation is a platform-admin-only operation
   (enforced by the API key dependency in the router, not in this layer).

2. **Establishment management** — creating, deleting, and reading
   establishments within an organisation.  Soft-delete is the default;
   hard-delete is available to platform admins only.

3. **Site equipment** — creating and listing equipment (e.g. cold rooms)
   attached to an establishment.  Equipment CRUD is gated behind
   ``ensure_admin_org_access``.

4. **Site users and assignments** — listing users assigned to a site and
   creating new user–role–site assignments (upsert semantics).

5. **Establishment settings** — reading and updating the JSONB feature-flag
   column on ``Etablissement``.  Only the organisation admin may modify
   settings.

6. **Organisation overview** — a single-query summary of all establishments,
   managers, and employees, used by the supervision dashboard.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentEstablishment, CurrentOrganisation
from app.core.role_utils import is_manager_role
from app.core.security import get_password_hash
from app.modules.equipments.models import Equipement
from app.modules.personnel.models import AffectationSite, Role, Utilisateur
from app.modules.personnel.service import ensure_admin_org_access, ensure_platform_admin_access
from app.modules.tenant.models import Abonnement, Etablissement, Organisation, StatutAbonnement
from app.modules.tenant.schemas import (
    AbonnementListItemResponse,
    AbonnementListResponse,
    EstablishmentCreateRequest,
    EstablishmentResponse,
    EstablishmentSettings,
    EstablishmentSettingsUpdateRequest,
    OrganisationCreateRequest,
    OrganisationResponse,
    OrganizationOverviewResponse,
    OrganizationSiteItem,
    OrganizationUserItem,
    PlanLimits,
    SiteAffectationCreateRequest,
    SiteAffectationResponse,
    SiteEquipmentCreateRequest,
    SiteEquipmentListResponse,
    SiteEquipmentResponse,
    SiteUserListItemResponse,
    SiteUserListResponse,
)

# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_site_in_manager_scope(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    etablissement_id: UUID,
    include_deleted: bool = False,
) -> Etablissement:
    """Load an establishment that is within the caller's organisation scope.

    Used as a guard before any operation that targets a specific establishment
    by UUID to enforce that the requesting manager cannot reach establishments
    outside their own organisation.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment
            context carrying the ``organisation_id`` for scope checking.
        etablissement_id (UUID): The target establishment's primary key.
        include_deleted (bool): When ``True``, soft-deleted establishments are
            included.  Required for hard-delete operations. Defaults to ``False``.

    Returns:
        Etablissement: The matching establishment ORM instance.

    Raises:
        HTTPException: 404 Not Found if no active establishment with that ID
            exists within the caller's organisation.
    """
    where_clauses = [
        Etablissement.id == etablissement_id,
        Etablissement.organisation_id == establishment.organisation_id,
    ]
    if not include_deleted:
        where_clauses.append(Etablissement.deleted_at.is_(None))

    result = await db.execute(select(Etablissement).where(*where_clauses))
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found in manager scope.",
        )
    return site


# ── Organisation ──────────────────────────────────────────────────────────────


async def create_organization(
    payload: OrganisationCreateRequest,
    db: AsyncSession,
) -> OrganisationResponse:
    """Create a new organisation tenant with an admin account.

    The admin password is hashed with bcrypt before storage.  A pre-check
    on ``admin_login_email`` uniqueness is performed before the INSERT to
    return a clean 409 instead of a database integrity error.

    Args:
        payload (OrganisationCreateRequest): Validated creation payload
            including the plain-text admin password.
        db (AsyncSession): The async database session.

    Returns:
        OrganisationResponse: The created organisation (password hash excluded).

    Raises:
        HTTPException: 409 Conflict if the admin email is already in use.
    """
    existing_result = await db.execute(
        select(Organisation).where(Organisation.admin_login_email == payload.admin_login_email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organisation already uses this admin login email.",
        )

    organization = Organisation(
        nom_entite=payload.nom_entite,
        type_secteur=payload.type_secteur,
        identifiant_legal=payload.identifiant_legal,
        admin_login_email=str(payload.admin_login_email),
        admin_password_hash=get_password_hash(payload.admin_password),
    )
    db.add(organization)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organisation creation conflicts with existing data.",
        ) from exc

    await db.refresh(organization)
    return OrganisationResponse(
        id=organization.id,
        nom_entite=organization.nom_entite,
        type_secteur=organization.type_secteur,
        identifiant_legal=organization.identifiant_legal,
        admin_login_email=organization.admin_login_email,
    )


async def list_organization_subscriptions(
    organisation_id: UUID,
    db: AsyncSession,
    current_org: CurrentOrganisation,
) -> AbonnementListResponse:
    """Return all billing subscriptions for the authenticated organisation.

    Args:
        organisation_id (UUID): The organisation whose subscriptions to list.
            Must match the JWT to prevent cross-tenant access.
        db (AsyncSession): The async database session.
        current_org (CurrentOrganisation): The authenticated organisation context.

    Returns:
        AbonnementListResponse: Subscriptions ordered by start date descending.

    Raises:
        HTTPException: 403 Forbidden if the JWT organisation does not match
            the requested ``organisation_id``.
    """
    if current_org.organisation_id != organisation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden organisation scope."
        )

    abonnements_result = await db.execute(
        select(Abonnement)
        .where(Abonnement.organisation_id == organisation_id)
        .order_by(Abonnement.date_debut.desc())
    )
    abonnements = abonnements_result.scalars().all()

    return AbonnementListResponse(
        items=[
            AbonnementListItemResponse(
                id=a.id,
                statut=a.statut,
                intervalle=a.intervalle,
                stripe_subscription_id=a.stripe_subscription_id,
                stripe_price_id=a.stripe_price_id,
                date_debut=a.date_debut,
                date_fin_periode=a.date_fin_periode,
            )
            for a in abonnements
        ]
    )


async def create_organization_establishment(
    organisation_id: UUID,
    payload: EstablishmentCreateRequest,
    db: AsyncSession,
    current_org: CurrentOrganisation,
) -> EstablishmentResponse:
    """Create a new establishment under the authenticated organisation.

    Validates SIRET uniqueness before the INSERT to avoid a database-level
    integrity error, which would surface as an opaque 500 without this guard.

    Args:
        organisation_id (UUID): Target organisation. Must match the JWT.
        payload (EstablishmentCreateRequest): Validated establishment data.
        db (AsyncSession): The async database session.
        current_org (CurrentOrganisation): The authenticated organisation context.

    Returns:
        EstablishmentResponse: The created establishment with default settings.

    Raises:
        HTTPException: 403 Forbidden if the JWT organisation does not match.
        HTTPException: 409 Conflict if the SIRET is already in use.
    """
    if current_org.organisation_id != organisation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden organisation scope."
        )

    if payload.siret is not None:
        existing_siret = await db.execute(
            select(Etablissement).where(Etablissement.siret == payload.siret)
        )
        if existing_siret.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SIRET already used.")

    etablissement = Etablissement(
        organisation_id=organisation_id,
        nom_site=payload.nom_site,
        adresse=payload.adresse,
        siret=payload.siret,
        type_activite=payload.type_activite,
        timezone=payload.timezone,
        telephone_site=payload.telephone_site,
    )
    db.add(etablissement)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Establishment creation conflicts."
        ) from exc

    await db.refresh(etablissement)
    return EstablishmentResponse(
        id=etablissement.id,
        organisation_id=etablissement.organisation_id,
        nom_site=etablissement.nom_site,
        adresse=etablissement.adresse,
        siret=etablissement.siret,
        type_activite=etablissement.type_activite,
        timezone=etablissement.timezone,
        telephone_site=etablissement.telephone_site,
        settings=EstablishmentSettings.from_raw(etablissement.settings or {}),
    )


async def delete_establishment(
    etablissement_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    hard_delete: bool = False,
) -> None:
    """Delete an establishment via soft delete (default) or hard delete (platform admin).

    Soft delete sets ``deleted_at`` to prevent the establishment from appearing
    in active queries while preserving its HACCP audit trail.  Hard delete
    physically removes the row and cascades to all child records; it is
    restricted to platform admins and blocked when the establishment being
    deleted is the one the caller is currently authenticated against.

    Args:
        etablissement_id (UUID): The establishment to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.
        hard_delete (bool): When ``True``, perform a physical delete instead of
            setting ``deleted_at``. Defaults to ``False``.

    Raises:
        HTTPException: 400 Bad Request if the caller tries to delete the
            establishment they are currently authenticated against.
        HTTPException: 403 Forbidden if the caller lacks the required rights.
        HTTPException: 404 Not Found if the establishment is not in scope.
    """
    if etablissement_id == establishment.etablissement_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the currently authenticated establishment.",
        )
    await ensure_admin_org_access(db, establishment)
    site = await _get_site_in_manager_scope(
        db, establishment, etablissement_id, include_deleted=hard_delete
    )
    if hard_delete:
        await ensure_platform_admin_access(db, establishment)
        await db.delete(site)
        await db.commit()
        return
    site.deleted_at = datetime.now(UTC)
    await db.commit()


# ── Site equipment ────────────────────────────────────────────────────────────


async def list_site_equipment(
    etablissement_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SiteEquipmentListResponse:
    """Return all active equipment for a specific establishment.

    Args:
        etablissement_id (UUID): The establishment whose equipment to list.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        SiteEquipmentListResponse: Equipment sorted by name.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the establishment is not in scope.
    """
    await ensure_admin_org_access(db, establishment)
    await _get_site_in_manager_scope(db, establishment, etablissement_id)

    equipements_result = await db.execute(
        select(Equipement)
        .where(Equipement.etablissement_id == etablissement_id, Equipement.deleted_at.is_(None))
        .order_by(Equipement.nom.asc())
    )
    equipements = equipements_result.scalars().all()

    return SiteEquipmentListResponse(
        items=[
            SiteEquipmentResponse(
                id=e.id,
                etablissement_id=e.etablissement_id,
                name=e.nom,
                equipment_type=e.type_equipement,
                min_target_temperature=e.temperature_min_cible,
                max_target_temperature=e.temperature_max_cible,
                is_active=e.deleted_at is None,
            )
            for e in equipements
        ]
    )


async def create_site_equipment(
    etablissement_id: UUID,
    payload: SiteEquipmentCreateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SiteEquipmentResponse:
    """Create a new piece of temperature-monitored equipment for an establishment.

    Args:
        etablissement_id (UUID): The target establishment.
        payload (SiteEquipmentCreateRequest): Validated equipment data
            including temperature thresholds.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        SiteEquipmentResponse: The created equipment record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the establishment is not in scope.
    """
    await ensure_admin_org_access(db, establishment)
    site = await _get_site_in_manager_scope(db, establishment, etablissement_id)

    equipement = Equipement(
        etablissement_id=site.id,
        nom=payload.name,
        type_equipement=payload.equipment_type,
        temperature_min_cible=payload.min_target_temperature,
        temperature_max_cible=payload.max_target_temperature,
    )
    db.add(equipement)
    await db.commit()
    await db.refresh(equipement)

    return SiteEquipmentResponse(
        id=equipement.id,
        etablissement_id=equipement.etablissement_id,
        name=equipement.nom,
        equipment_type=equipement.type_equipement,
        min_target_temperature=equipement.temperature_min_cible,
        max_target_temperature=equipement.temperature_max_cible,
        is_active=equipement.deleted_at is None,
    )


# ── Site users ────────────────────────────────────────────────────────────────


async def list_site_users(
    etablissement_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SiteUserListResponse:
    """Return all user–role assignments for a specific establishment.

    Args:
        etablissement_id (UUID): The establishment whose users to list.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        SiteUserListResponse: All non-deleted users with their role and
            assignment status.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the establishment is not in scope.
    """
    await ensure_admin_org_access(db, establishment)
    await _get_site_in_manager_scope(db, establishment, etablissement_id)

    assignments_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.utilisateur), selectinload(AffectationSite.role))
        .where(AffectationSite.etablissement_id == etablissement_id)
    )
    assignments = assignments_result.scalars().all()

    return SiteUserListResponse(
        items=[
            SiteUserListItemResponse(
                utilisateur_id=a.utilisateur_id,
                nom=a.utilisateur.nom,
                prenom=a.utilisateur.prenom,
                email=a.utilisateur.email,
                role_id=a.role_id,
                role_name=a.role.nom_role,
                is_active=a.is_active,
            )
            for a in assignments
            if a.utilisateur is not None and a.utilisateur.deleted_at is None and a.role is not None
        ]
    )


async def create_site_affectation(
    etablissement_id: UUID,
    payload: SiteAffectationCreateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> SiteAffectationResponse:
    """Create or update a user–role assignment for an establishment (upsert).

    If an assignment already exists for the same user/establishment/role
    triple, its ``poste_principal`` and ``is_active`` fields are updated
    instead of creating a duplicate row.

    Args:
        etablissement_id (UUID): The target establishment.
        payload (SiteAffectationCreateRequest): Assignment parameters.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        SiteAffectationResponse: The created or updated assignment.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the establishment or role is not found.
    """
    await ensure_admin_org_access(db, establishment)
    site = await _get_site_in_manager_scope(db, establishment, etablissement_id)

    role_result = await db.execute(select(Role).where(Role.id == payload.role_id))
    role = role_result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    existing_result = await db.execute(
        select(AffectationSite).where(
            AffectationSite.utilisateur_id == payload.utilisateur_id,
            AffectationSite.etablissement_id == site.id,
            AffectationSite.role_id == payload.role_id,
        )
    )
    assignment = existing_result.scalar_one_or_none()

    if assignment is None:
        assignment = AffectationSite(
            utilisateur_id=payload.utilisateur_id,
            etablissement_id=site.id,
            role_id=payload.role_id,
            poste_principal=payload.poste_principal,
            is_active=payload.is_active,
        )
        db.add(assignment)
    else:
        assignment.poste_principal = payload.poste_principal
        assignment.is_active = payload.is_active

    await db.commit()
    return SiteAffectationResponse(
        utilisateur_id=assignment.utilisateur_id,
        etablissement_id=assignment.etablissement_id,
        role_id=assignment.role_id,
        poste_principal=assignment.poste_principal,
        is_active=assignment.is_active,
    )


# ── Establishment settings ────────────────────────────────────────────────────


async def get_establishment_settings(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> EstablishmentSettings:
    """Return the current feature-flag settings for the authenticated establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        EstablishmentSettings: Settings with defaults applied for any missing
            keys in the stored JSONB.
    """
    result = await db.execute(
        select(Etablissement.settings).where(Etablissement.id == establishment.etablissement_id)
    )
    raw = result.scalar_one_or_none() or {}
    return EstablishmentSettings.from_raw(raw)


async def update_establishment_settings(
    payload: EstablishmentSettingsUpdateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> EstablishmentSettings:
    """Apply a partial update to the establishment's feature-flag settings.

    Only the organisation admin (``is_org_admin`` claim in the JWT) may
    modify settings.  Non-admin managers can read settings but not write them.

    Args:
        payload (EstablishmentSettingsUpdateRequest): Sub-models to merge
            into the existing settings.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        EstablishmentSettings: The fully merged settings after the update.

    Raises:
        HTTPException: 403 Forbidden if the caller is not the organisation admin.
        HTTPException: 404 Not Found if the establishment no longer exists.
    """
    if not establishment.is_org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul l'administrateur de l'organisation peut modifier ces paramètres.",
        )
    result = await db.execute(
        select(Etablissement).where(Etablissement.id == establishment.etablissement_id)
    )
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Establishment not found."
        )

    current = EstablishmentSettings.from_raw(site.settings or {})
    updates = payload.model_dump(exclude_none=True)
    if updates:
        current = current.model_copy(update=updates)

    site.settings = current.model_dump()
    await db.commit()
    return current


# ── Plan limits ──────────────────────────────────────────────────────────────


async def get_plan_limits(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> PlanLimits:
    """Return the feature limits granted by the organisation's active subscription.

    Falls back to generous defaults when no active or trialing subscription exists,
    so that existing accounts without a subscription are never accidentally blocked.
    """
    result = await db.execute(
        select(Abonnement)
        .where(
            Abonnement.organisation_id == establishment.organisation_id,
            Abonnement.statut.in_([StatutAbonnement.ACTIVE, StatutAbonnement.TRIALING]),
        )
        .order_by(Abonnement.date_debut.desc())
        .limit(1)
    )
    abonnement = result.scalar_one_or_none()
    if abonnement is None:
        return PlanLimits()
    return PlanLimits.from_subscription(abonnement.features_limits or {})


# ── Organisation overview ─────────────────────────────────────────────────────


async def organization_overview(
    organization: CurrentOrganisation,
    db: AsyncSession,
) -> OrganizationOverviewResponse:
    """Build the full organisation supervision dashboard payload.

    Executes two queries — one for establishments, one for all user assignments
    across those establishments — and merges them in Python to produce a
    structured overview without additional round-trips.

    Users are split into ``managers`` (any assignment with a manager-grade role)
    and ``employees`` (everyone else).  A user holding both a manager and a
    non-manager role on different sites is classified as a manager.

    Args:
        organization (CurrentOrganisation): The authenticated organisation context.
        db (AsyncSession): The async database session.

    Returns:
        OrganizationOverviewResponse: Establishments, managers, and employees
            sorted alphabetically by last name then first name.
    """
    establishments_result = await db.execute(
        select(Etablissement)
        .where(
            Etablissement.organisation_id == organization.organisation_id,
            Etablissement.deleted_at.is_(None),
        )
        .order_by(Etablissement.nom_site.asc())
    )
    establishments = establishments_result.scalars().all()

    assignments_result = await db.execute(
        select(AffectationSite)
        .join(Etablissement, Etablissement.id == AffectationSite.etablissement_id)
        .join(Utilisateur, Utilisateur.id == AffectationSite.utilisateur_id)
        .where(
            Etablissement.organisation_id == organization.organisation_id,
            Etablissement.deleted_at.is_(None),
            Utilisateur.deleted_at.is_(None),
        )
        .options(
            selectinload(AffectationSite.role),
            selectinload(AffectationSite.utilisateur),
            selectinload(AffectationSite.etablissement),
        )
    )
    assignments = assignments_result.scalars().all()

    # Aggregate per-user data across all assignments in Python to avoid a
    # complex multi-level GROUP BY that would be harder to read and maintain.
    by_user: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        user = assignment.utilisateur
        site = assignment.etablissement
        if user is None or site is None:
            continue
        user_key = str(user.id)
        role_name = assignment.role.nom_role if assignment.role is not None else None
        if user_key not in by_user:
            by_user[user_key] = {
                "id": user.id,
                "nom": user.nom,
                "prenom": user.prenom,
                "email": user.email,
                "role": role_name,
                "manager": is_manager_role(assignment.role),
                "sites": set(),
            }
        by_user[user_key]["manager"] = by_user[user_key]["manager"] or is_manager_role(
            assignment.role
        )
        if role_name and not by_user[user_key]["role"]:
            by_user[user_key]["role"] = role_name
        by_user[user_key]["sites"].add(site.nom_site)

    managers: list[OrganizationUserItem] = []
    employees: list[OrganizationUserItem] = []
    for row in by_user.values():
        item = OrganizationUserItem(
            id=row["id"],
            last_name=row["nom"],
            first_name=row["prenom"],
            email=row["email"],
            role=row["role"],
            site_names=sorted(row["sites"]),
        )
        (managers if row["manager"] else employees).append(item)

    managers.sort(key=lambda i: (i.last_name.lower(), i.first_name.lower()))
    employees.sort(key=lambda i: (i.last_name.lower(), i.first_name.lower()))

    return OrganizationOverviewResponse(
        organization_id=organization.organisation_id,
        organization_name=organization.nom_entite,
        establishments=[
            OrganizationSiteItem(id=s.id, site_name=s.nom_site, timezone=s.timezone)
            for s in establishments
        ],
        managers=managers,
        employees=employees,
    )
