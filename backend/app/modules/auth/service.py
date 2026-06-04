"""
Business logic for the Authentication domain.

This module handles the two distinct login flows and the post-login operator
session resolution:

1. **Manager login** — validates email + password, checks that the manager has
   an active assignment with a manager-grade role on the requested establishment,
   and issues a long-lived establishment JWT that locks the device to that site.

2. **Organisation login** — validates the organisation admin email + password
   and issues an organisation-level supervision JWT.

3. **Operator session** — called after a manager JWT is already verified.  Given
   the authenticated operator (resolved by the PIN dependency), it returns a safe
   profile payload used by the tablet frontend to configure the operator session.

4. **Operator list** — returns all active operators for the locked establishment
   so the tablet can display the profile selection screen.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentEstablishment
from app.core.role_utils import is_manager_role
from app.core.security import (
    create_establishment_access_token,
    verify_password,
)
from app.core.security import (
    create_organisation_access_token as create_organization_access_token,
)
from app.modules.auth.schemas import (
    EstablishmentPublicResponse,
    EstablishmentTokenMetadata,
    ManagerLoginRequest,
    OperatorListItemResponse,
    OrganisationLoginRequest,
    OrganisationTokenMetadata,
    OrganisationTokenResponse,
    TokenResponse,
)
from app.modules.personnel.models import AffectationSite, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation


async def read_establishment_public_metadata(
    etablissement_id: str,
    db: AsyncSession,
) -> EstablishmentPublicResponse:
    """Return public establishment metadata for the device setup screen.

    Called before authentication — no token required.  Filtered to
    non-deleted establishments only to prevent enumeration of decommissioned sites.

    Args:
        etablissement_id (str): The establishment's UUID as a string.
        db (AsyncSession): The async database session.

    Returns:
        EstablishmentPublicResponse: Site name and timezone for display.

    Raises:
        HTTPException: 404 Not Found if the establishment does not exist or is
            soft-deleted.
    """
    establishment_result = await db.execute(
        select(Etablissement).where(
            Etablissement.id == etablissement_id,
            Etablissement.deleted_at.is_(None),
        )
    )
    etablissement = establishment_result.scalar_one_or_none()
    if etablissement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Establishment not found."
        )

    return EstablishmentPublicResponse(
        etablissement_id=etablissement.id,
        nom_site=etablissement.nom_site,
        timezone=etablissement.timezone,
    )


async def login_manager(
    payload: ManagerLoginRequest,
    db: AsyncSession,
) -> TokenResponse:
    """Authenticate a manager and issue a device JWT locking the tablet to one establishment.

    Performs three checks in sequence:
    1. Email + password match a non-deleted ``Utilisateur``.
    2. The requested establishment is non-deleted.
    3. The manager holds an active assignment with a manager-grade role on that establishment.

    The ``is_org_admin`` claim is set by comparing the manager's email to the
    organisation's ``admin_login_email``, granting cross-establishment management
    permissions when they match.

    Args:
        payload (ManagerLoginRequest): Login credentials and target establishment.
        db (AsyncSession): The async database session.

    Returns:
        TokenResponse: The signed establishment JWT and safe site metadata.

    Raises:
        HTTPException: 401 Unauthorized for invalid credentials (same message
            for wrong email and wrong password to prevent enumeration).
        HTTPException: 404 Not Found if the establishment does not exist.
        HTTPException: 403 Forbidden if the manager is not assigned to the
            requested establishment with a manager-grade role.
    """
    user_result = await db.execute(
        select(Utilisateur).where(
            Utilisateur.email == payload.email,
            Utilisateur.deleted_at.is_(None),
        )
    )
    manager = user_result.scalar_one_or_none()
    # Combining the "user not found" and "wrong password" cases into a single
    # 401 prevents email enumeration attacks.
    if manager is None or not verify_password(payload.password, manager.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid manager credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    establishment_result = await db.execute(
        select(Etablissement).where(
            Etablissement.id == payload.etablissement_id,
            Etablissement.deleted_at.is_(None),
        )
    )
    etablissement = establishment_result.scalar_one_or_none()
    if etablissement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Establishment not found."
        )

    assignment_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.role))
        .where(
            AffectationSite.utilisateur_id == manager.id,
            AffectationSite.etablissement_id == etablissement.id,
            AffectationSite.is_active.is_(True),
        )
    )
    active_assignments = assignment_result.scalars().all()

    if not any(is_manager_role(assignment.role) for assignment in active_assignments):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager is not allowed to access this establishment.",
        )

    # Determine org-admin status by comparing email — avoids an extra DB join.
    org_result = await db.execute(
        select(Organisation.admin_login_email).where(
            Organisation.id == etablissement.organisation_id
        )
    )
    org_admin_email = org_result.scalar_one_or_none()
    is_org_admin = org_admin_email is not None and manager.email == org_admin_email

    access_token = create_establishment_access_token(
        {
            "organisation_id": str(etablissement.organisation_id),
            "etablissement_id": str(etablissement.id),
            "utilisateur_id": str(manager.id),
            "is_org_admin": is_org_admin,
        }
    )

    return TokenResponse(
        access_token=access_token,
        establishment=EstablishmentTokenMetadata(
            organisation_id=etablissement.organisation_id,
            etablissement_id=etablissement.id,
            nom_site=etablissement.nom_site,
            timezone=etablissement.timezone,
            is_org_admin=is_org_admin,
        ),
    )


async def login_organization(
    payload: OrganisationLoginRequest,
    db: AsyncSession,
) -> OrganisationTokenResponse:
    """Authenticate an organisation admin and issue a supervision JWT.

    Args:
        payload (OrganisationLoginRequest): Login credentials.
        db (AsyncSession): The async database session.

    Returns:
        OrganisationTokenResponse: The signed organisation JWT and safe metadata.

    Raises:
        HTTPException: 401 Unauthorized if the credentials are invalid or the
            organisation has no admin password set (i.e. no hash in the DB).
    """
    organization_result = await db.execute(
        select(Organisation).where(Organisation.admin_login_email == payload.email)
    )
    organization = organization_result.scalar_one_or_none()
    if (
        organization is None
        or organization.admin_password_hash is None
        or not verify_password(payload.password, organization.admin_password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organisation credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_organization_access_token({"organisation_id": str(organization.id)})

    return OrganisationTokenResponse(
        access_token=access_token,
        organisation=OrganisationTokenMetadata(
            organisation_id=organization.id,
            nom_entite=organization.nom_entite,
        ),
    )


async def read_current_operator(
    establishment: CurrentEstablishment,
    operator: Utilisateur,
    db: AsyncSession,
) -> dict[str, Any]:
    """Build the operator session payload after a successful PIN authentication.

    Called immediately after the ``get_current_operator`` dependency resolves.
    Returns a structured dictionary (not a Pydantic schema) to accommodate the
    flexible permissions map from ``Role.permissions``.

    Args:
        establishment (CurrentEstablishment): The authenticated device context.
        operator (Utilisateur): The PIN-authenticated operator.
        db (AsyncSession): The async database session.

    Returns:
        dict[str, Any]: Nested dict with ``"establishment"`` and ``"operator"``
            keys used by the tablet frontend to configure the active session.
    """
    assignment_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.role))
        .where(
            AffectationSite.utilisateur_id == operator.id,
            AffectationSite.etablissement_id == establishment.etablissement_id,
            AffectationSite.is_active.is_(True),
        )
    )
    assignments = assignment_result.scalars().all()
    first_role = assignments[0].role if assignments else None
    is_admin = any(is_manager_role(assignment.role) for assignment in assignments)

    return {
        "establishment": {
            "id": str(establishment.etablissement_id),
            "nom_site": establishment.nom_site,
        },
        "operator": {
            "id": str(operator.id),
            "nom": operator.nom,
            "prenom": operator.prenom,
            "email": operator.email,
            "role": first_role.nom_role if first_role else None,
            "permissions": first_role.permissions if first_role else {},
            "is_admin": is_admin,
        },
    }


async def list_operators_for_current_establishment(
    establishment: CurrentEstablishment,
    db: AsyncSession,
) -> list[OperatorListItemResponse]:
    """Return all active operators assigned to the locked establishment.

    Used by the tablet profile-selection screen.  A deduplication step ensures
    each ``Utilisateur`` appears at most once even if they hold multiple roles.

    Args:
        establishment (CurrentEstablishment): The authenticated device context.
        db (AsyncSession): The async database session.

    Returns:
        list[OperatorListItemResponse]: Active operators sorted alphabetically
            by last name then first name.
    """
    assignments_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.utilisateur), selectinload(AffectationSite.role))
        .where(
            AffectationSite.etablissement_id == establishment.etablissement_id,
            AffectationSite.is_active.is_(True),
        )
    )
    assignments = assignments_result.scalars().all()

    operators: list[OperatorListItemResponse] = []
    seen_user_ids: set[str] = set()

    for assignment in assignments:
        user = assignment.utilisateur
        if user is None or user.deleted_at is not None:
            continue
        user_key = str(user.id)
        # Skip duplicate user IDs that appear when a user holds multiple roles.
        if user_key in seen_user_ids:
            continue
        seen_user_ids.add(user_key)

        role_name = assignment.role.nom_role if assignment.role is not None else None
        operators.append(
            OperatorListItemResponse(
                id=user.id,
                nom=user.nom,
                prenom=user.prenom,
                email=user.email,
                nom_complet=f"{user.prenom} {user.nom}".strip(),
                role=role_name,
                role_id=assignment.role_id,
                is_active=assignment.is_active,
            )
        )

    operators.sort(key=lambda item: (item.nom.lower(), item.prenom.lower()))
    return operators
