"""
FastAPI router for the Authentication domain.

Exposes the following public and authenticated endpoints:

- ``POST /organisation-sessions`` — organisation admin login.
- ``POST /establishment-sessions`` — manager device login (pins tablet to site).
- ``GET  /establishments/{etablissement_id}`` — public site metadata (pre-auth).
- ``POST /operator-sessions`` — operator PIN session resolution.
- ``GET  /establishments/{etablissement_id}/users`` — operator list for the
  shared-tablet profile-selection screen.

All write operations are handled by the :mod:`app.modules.auth.service` layer;
the router is responsible only for HTTP plumbing and input validation.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession
from app.modules.auth import service
from app.modules.auth.schemas import (
    EstablishmentPublicResponse,
    ManagerLoginRequest,
    OperatorListItemResponse,
    OrganisationLoginRequest,
    OrganisationTokenResponse,
    TokenResponse,
)

router = APIRouter(tags=["Authentication"])


@router.post("/organisation-sessions", response_model=OrganisationTokenResponse)
async def create_organization_session(
    payload: OrganisationLoginRequest,
    db: DatabaseSession,
) -> OrganisationTokenResponse:
    """Authenticate an organisation admin and issue a supervision JWT.

    Args:
        payload (OrganisationLoginRequest): Email and password for the
            organisation admin account.
        db (DatabaseSession): Injected async database session.

    Returns:
        OrganisationTokenResponse: Signed organisation JWT and safe metadata.

    Raises:
        HTTPException: 401 Unauthorized for invalid credentials.
    """
    return await service.login_organization(payload, db)


@router.post("/establishment-sessions", response_model=TokenResponse)
async def create_establishment_session(
    payload: ManagerLoginRequest,
    db: DatabaseSession,
) -> TokenResponse:
    """Authenticate a manager and lock a shared device to one establishment.

    Args:
        payload (ManagerLoginRequest): Manager credentials and target
            establishment UUID.
        db (DatabaseSession): Injected async database session.

    Returns:
        TokenResponse: Signed establishment JWT and safe site metadata.

    Raises:
        HTTPException: 401 Unauthorized for invalid credentials.
        HTTPException: 404 Not Found if the establishment does not exist.
        HTTPException: 403 Forbidden if the manager lacks a manager role
            on the requested establishment.
    """
    return await service.login_manager(payload, db)


@router.get("/establishments/{etablissement_id}", response_model=EstablishmentPublicResponse)
async def read_establishment_metadata(
    etablissement_id: UUID,
    db: DatabaseSession,
) -> EstablishmentPublicResponse:
    """Return public establishment metadata for the device setup screen.

    No authentication required — called before the manager logs in to
    confirm the QR-code or establishment ID they entered is correct.

    Args:
        etablissement_id (UUID): The establishment's primary key.
        db (DatabaseSession): Injected async database session.

    Returns:
        EstablishmentPublicResponse: Site name and timezone.

    Raises:
        HTTPException: 404 Not Found if the establishment does not exist
            or has been soft-deleted.
    """
    return await service.read_establishment_public_metadata(etablissement_id, db)


@router.post("/operator-sessions")
async def create_operator_session(
    establishment: CurrentSite,
    operator: CurrentOperator,
    db: DatabaseSession,
) -> dict[str, Any]:
    """Build the operator session payload after a successful PIN authentication.

    Both the establishment JWT (``CurrentSite``) and the operator PIN
    (``CurrentOperator``) are validated by FastAPI dependencies before this
    handler runs.

    Args:
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.
        db (DatabaseSession): Injected async database session.

    Returns:
        dict[str, Any]: Nested dict with ``"establishment"`` and ``"operator"``
            keys used by the tablet frontend.
    """
    return await service.read_current_operator(establishment, operator, db)


@router.get(
    "/establishments/{etablissement_id}/users", response_model=list[OperatorListItemResponse]
)
async def list_establishment_users(
    etablissement_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    role: Annotated[str | None, Query()] = None,
) -> list[OperatorListItemResponse]:
    """List active operators for the locked establishment's profile-selection screen.

    An optional ``role`` query parameter is supported for API forward-compatibility
    but currently only ``SITE_EMPLOYEE`` is accepted.

    Args:
        etablissement_id (UUID): Must match the establishment from the JWT to
            prevent cross-tenant data access.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        role (str | None): Optional role filter; only ``"SITE_EMPLOYEE"`` is
            supported.

    Returns:
        list[OperatorListItemResponse]: Alphabetically sorted active operators.

    Raises:
        HTTPException: 403 Forbidden if ``etablissement_id`` does not match
            the JWT-locked establishment.
        HTTPException: 400 Bad Request for unsupported ``role`` filter values.
    """
    from fastapi import HTTPException
    from fastapi import status as http_status

    if etablissement_id != establishment.etablissement_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Forbidden establishment scope.",
        )
    if role is not None and role.upper() != "SITE_EMPLOYEE":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Only role=SITE_EMPLOYEE filter is currently supported.",
        )
    return await service.list_operators_for_current_establishment(establishment, db)
