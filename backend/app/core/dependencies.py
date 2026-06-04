"""
Core FastAPI dependency functions for authentication and authorization.

This module defines the two primary authentication flows used throughout the
application:

1. **Establishment-level (shared-device) JWT** — A long-lived token that locks
   a shared kitchen tablet to one establishment.  It embeds the
   ``etablissement_id`` and ``utilisateur_id`` (the manager who set up the
   device), enabling Row-Level Security on every subsequent request.

2. **Organisation-level JWT** — A separate token for cross-establishment
   supervision dashboards.  It carries only the ``organisation_id``.

Both tokens are validated on every request via FastAPI ``Depends`` injection.
No token is ever cached in memory; each request performs a fresh DB lookup to
catch revoked or deleted records.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.role_utils import is_manager_role
from app.core.security import (
    decode_establishment_access_token,
    decode_organisation_access_token,
    verify_password,
)
from app.modules.personnel.models import AffectationSite, Utilisateur
from app.modules.tenant.models import Etablissement, Organisation

# ---------------------------------------------------------------------------
# OAuth2 scheme declarations — used by FastAPI's OpenAPI documentation to
# surface the correct "Authorize" flow in Swagger UI.
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login/manager",
    scheme_name="ManagerAuth",
)
oauth2_organisation_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login/organisation",
    scheme_name="OrganisationAuth",
)

# Typed aliases for FastAPI dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
BearerToken = Annotated[str, Depends(oauth2_scheme)]
OrganisationBearerToken = Annotated[str, Depends(oauth2_organisation_scheme)]

# Tablet operator headers — both are required simultaneously to authenticate
# an operator action.  The 4-digit PIN is validated client-side for UX and
# server-side for security; the operator ID prevents brute-force PIN guessing
# against an anonymous target.
DevicePinHeader = Annotated[
    str,
    Header(..., alias="X-Device-Pin", min_length=4, max_length=4, pattern=r"^\d{4}$"),
]
DeviceOperatorIdHeader = Annotated[
    str,
    Header(..., alias="X-Operator-Id", min_length=36, max_length=36),
]


class CurrentEstablishment(BaseModel):
    """Immutable authentication context decoded from a shared-device establishment JWT.

    An instance of this model is injected into every endpoint that requires
    manager-level or operator-level access.  It acts as the Row-Level Security
    boundary: all database queries MUST filter by ``etablissement_id`` to prevent
    cross-tenant data leakage.

    Attributes:
        organisation_id (UUID): The owning organisation.
        etablissement_id (UUID): The locked establishment for this device session.
        nom_site (str): Human-readable site name, used in audit logs.
        timezone (str): IANA timezone string (e.g. ``"Europe/Paris"``), used to
            compute site-local timestamps for HACCP records.
        manager_user_id (UUID): The ``Utilisateur`` who generated the token.
        is_org_admin (bool): Whether the token holder is the organisation admin.
            Grants access to cross-establishment management endpoints.
        settings (dict): Establishment-level feature flags (e.g. timeclock toggle).
    """

    organisation_id: UUID
    etablissement_id: UUID
    nom_site: str
    timezone: str
    manager_user_id: UUID
    is_org_admin: bool = False
    settings: dict = {}


class CurrentOrganisation(BaseModel):
    """Immutable authentication context decoded from an organisation supervision JWT.

    Scoped to organisation-wide supervision endpoints such as the multi-site
    dashboard and establishment management.

    Attributes:
        organisation_id (UUID): The authenticated organisation's primary key.
        nom_entite (str): Legal entity name of the organisation.
    """

    organisation_id: UUID
    nom_entite: str


async def get_current_establishment(
    token: BearerToken,
    db: DatabaseSession,
) -> CurrentEstablishment:
    """Validate a shared-device JWT and return the locked establishment context.

    Performs two validation steps:
    1. Cryptographic JWT signature and claims extraction.
    2. Live database lookup to confirm the establishment still exists and has
       not been soft-deleted, preventing stale tokens from granting access after
       an establishment is decommissioned.

    Args:
        token (str): The Bearer token extracted from the ``Authorization`` header.
        db (AsyncSession): The injected async database session.

    Returns:
        CurrentEstablishment: A fully populated context object for the request.

    Raises:
        HTTPException: 401 Unauthorized if the JWT is malformed, expired, or
            references a deleted/non-existent establishment.
    """
    try:
        payload = decode_establishment_access_token(token)
        etablissement_id = UUID(str(payload["etablissement_id"]))
        organisation_id = UUID(str(payload["organisation_id"]))
        manager_user_id = UUID(str(payload["utilisateur_id"]))
        is_org_admin = bool(payload.get("is_org_admin", False))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid establishment token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(
        select(Etablissement).where(
            Etablissement.id == etablissement_id,
            Etablissement.organisation_id == organisation_id,
            # Soft-deleted establishments must not be accessible even with a
            # valid, unexpired token to prevent access after decommissioning.
            Etablissement.deleted_at.is_(None),
        )
    )
    etablissement = result.scalar_one_or_none()
    if etablissement is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Establishment token is no longer valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentEstablishment(
        organisation_id=etablissement.organisation_id,
        etablissement_id=etablissement.id,
        nom_site=etablissement.nom_site,
        timezone=etablissement.timezone,
        manager_user_id=manager_user_id,
        is_org_admin=is_org_admin,
        settings=etablissement.settings or {},
    )


async def get_current_organisation(
    token: OrganisationBearerToken,
    db: DatabaseSession,
) -> CurrentOrganisation:
    """Validate an organisation supervision JWT and return the tenant context.

    Args:
        token (str): The Bearer token extracted from the ``Authorization`` header.
        db (AsyncSession): The injected async database session.

    Returns:
        CurrentOrganisation: The authenticated organisation context.

    Raises:
        HTTPException: 401 Unauthorized if the JWT is invalid or the organisation
            no longer exists.
    """
    try:
        payload = decode_organisation_access_token(token)
        organisation_id = UUID(str(payload["organisation_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organisation token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(select(Organisation).where(Organisation.id == organisation_id))
    organisation = result.scalar_one_or_none()
    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organisation token is no longer valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentOrganisation(
        organisation_id=organisation.id,
        nom_entite=organisation.nom_entite,
    )


# Internal API-key header reader — ``auto_error=False`` lets us return a clean
# 401 instead of FastAPI's default 403 when the header is absent.
_platform_admin_key_header = APIKeyHeader(name="X-Platform-Admin-Key", auto_error=False)


async def require_platform_admin_key(
    key: Annotated[str | None, Security(_platform_admin_key_header)],
) -> None:
    """Enforce that the caller supplies the correct platform-level admin API key.

    This guard protects irreversible platform operations such as organisation
    creation and hard-delete.  It is intentionally separate from the JWT-based
    flows so that platform admin tooling can operate without a user session.

    Args:
        key (str | None): The value of the ``X-Platform-Admin-Key`` request header,
            or ``None`` if the header is absent.

    Raises:
        HTTPException: 401 Unauthorized if the key is absent or does not match
            the configured ``PLATFORM_ADMIN_KEY`` secret.
    """
    if not key or key != settings.PLATFORM_ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid X-Platform-Admin-Key header is required.",
        )


async def get_current_operator(
    x_device_pin: DevicePinHeader,
    x_operator_id: DeviceOperatorIdHeader,
    db: DatabaseSession,
    establishment: Annotated[CurrentEstablishment, Depends(get_current_establishment)],
) -> Utilisateur:
    """Authenticate an operator on the shared tablet via site-assignment lookup and PIN check.

    This dependency is layered on top of ``get_current_establishment``: the
    device JWT must already be valid before the operator PIN is evaluated.  The
    two-step authentication (device JWT + operator PIN) ensures that even if an
    operator's PIN is leaked, it cannot be used from an unauthorised device.

    The function deliberately returns the same generic error for all failure
    modes (missing assignment, deleted user, manager role, wrong PIN) to prevent
    enumeration attacks.

    Args:
        x_device_pin (str): 4-digit PIN supplied in the ``X-Device-Pin`` header.
        x_operator_id (str): UUID string of the operator in the ``X-Operator-Id`` header.
        db (AsyncSession): The injected async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        Utilisateur: The authenticated operator's ORM instance, confirmed active
            and assigned to the locked establishment.

    Raises:
        HTTPException: 400 Bad Request if ``x_operator_id`` is not a valid UUID.
        HTTPException: 401 Unauthorized for any authentication failure (missing
            assignment, soft-deleted user, manager role attempted on operator
            endpoint, or incorrect PIN).
    """
    try:
        operator_id = UUID(x_operator_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operator identifier.",
        ) from exc

    result = await db.execute(
        select(AffectationSite)
        .options(
            selectinload(AffectationSite.utilisateur),
            selectinload(AffectationSite.role),
        )
        .where(
            AffectationSite.utilisateur_id == operator_id,
            AffectationSite.etablissement_id == establishment.etablissement_id,
            AffectationSite.is_active.is_(True),
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credentials.",
        )

    utilisateur = assignment.utilisateur
    role = assignment.role

    if (
        utilisateur is None
        or utilisateur.deleted_at is not None
        or role is None
        # Managers are not permitted to sign HACCP actions via the operator PIN
        # flow; they must use the manager JWT endpoint instead.
        or is_manager_role(role)
        or utilisateur.code_pin is None
        or not verify_password(x_device_pin, utilisateur.code_pin)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credentials.",
        )

    return utilisateur
