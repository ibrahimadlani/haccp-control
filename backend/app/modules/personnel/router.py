"""
FastAPI router for the Personnel domain.

Exposes CRUD endpoints for two distinct sub-domains:

**Roles:**
- ``GET /roles`` — list available platform roles for assignment forms.

**Users (collaborators):**
- ``GET    /users`` — list collaborators assigned within the current organisation.
- ``POST   /users`` — create a new collaborator with establishment assignments.
- ``PATCH  /users/{utilisateur_id}`` — partially update a collaborator's profile.
- ``DELETE /users/{utilisateur_id}`` — soft-delete (default) or hard-delete a collaborator.

**Operators (tablet PIN staff):**
- ``GET    /operators`` — list operators for the current establishment.
- ``POST   /operators`` — register a new tablet operator.
- ``PATCH  /operators/{operator_id}`` — update an operator's profile.
- ``POST   /operators/{operator_id}/reset-pin`` — replace an operator's PIN.
- ``DELETE /operators/{operator_id}`` — soft-deactivate an operator.

All endpoints require a valid establishment JWT (``CurrentSite``).  Write
operations on users additionally require manager rights, enforced in the
service layer via ``ensure_admin_org_access``.  Operator deactivation never
physically removes the row to preserve historical HACCP audit trail integrity.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.modules.personnel import service
from app.modules.personnel.schemas import (
    OperatorCreate,
    OperatorListResponse,
    OperatorResponse,
    OperatorUpdate,
    PinResetRequest,
    RoleListItemResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserListItemResponse,
    UserUpdateRequest,
)

router = APIRouter(tags=["Personnel"])


# ── Roles ─────────────────────────────────────────────────────────────────────


@router.get("/roles", response_model=list[RoleListItemResponse])
async def list_roles(db: DatabaseSession, establishment: CurrentSite) -> list[RoleListItemResponse]:
    """Return all available roles for use in assignment forms.

    Roles are platform-wide (not scoped to an organisation).  Access is
    gated by manager rights to prevent operators from enumerating roles.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        list[RoleListItemResponse]: All roles sorted alphabetically.
    """
    return await service.list_roles(db, establishment)


# ── Users ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserListItemResponse])
async def list_users(db: DatabaseSession, establishment: CurrentSite) -> list[UserListItemResponse]:
    """List all collaborators assigned within the current organisation.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        list[UserListItemResponse]: Collaborators sorted by last name, then first name.
    """
    return await service.list_users(db, establishment)


@router.post("/users", response_model=UserCreateResponse, status_code=201)
async def create_user(
    payload: UserCreateRequest, db: DatabaseSession, establishment: CurrentSite
) -> UserCreateResponse:
    """Create a new collaborator and assign them to one or more establishments.

    Args:
        payload (UserCreateRequest): Collaborator data including plain-text
            password, PIN, role, and establishment IDs.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        UserCreateResponse: The new user's ID, email, and assigned establishments.

    Raises:
        HTTPException: 400 Bad Request if the email is already taken.
        HTTPException: 404 Not Found if the role does not exist.
    """
    return await service.create_user(payload, db, establishment)


@router.patch("/users/{utilisateur_id}", response_model=UserListItemResponse)
async def update_user(
    utilisateur_id: UUID,
    payload: UserUpdateRequest,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> UserListItemResponse:
    """Partially update a collaborator's profile (PATCH semantics).

    Supplying ``role_id`` or ``establishment_ids`` triggers a full rebuild
    of the user's site assignments for the current organisation.

    Args:
        utilisateur_id (UUID): The collaborator to update.
        payload (UserUpdateRequest): Fields to update.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        UserListItemResponse: The updated collaborator's full profile.
    """
    return await service.update_user(utilisateur_id, payload, db, establishment)


@router.delete("/users/{utilisateur_id}", status_code=204)
async def delete_user(
    utilisateur_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    hard_delete: bool = Query(default=False),
) -> None:
    """Delete a collaborator (soft by default, hard for platform admins).

    Soft delete sets ``deleted_at`` and deactivates all assignments,
    preserving the user's historical HACCP records.

    Args:
        utilisateur_id (UUID): The collaborator to delete.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        hard_delete (bool): Physical delete when ``True``. Requires platform-admin
            rights and will be blocked if the user belongs to another org.
    """
    return await service.delete_user(utilisateur_id, db, establishment, hard_delete=hard_delete)


# ── Operators ─────────────────────────────────────────────────────────────────


@router.get("/operators", response_model=OperatorListResponse, dependencies=[Depends(require_feature(Feature.OPERATORS))])
async def list_operators(
    db: DatabaseSession,
    establishment: CurrentSite,
    include_inactive: Annotated[bool, Query()] = False,
) -> OperatorListResponse:
    """List operators registered for the current establishment.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        include_inactive (bool): Include soft-deleted operators. Defaults to ``False``.

    Returns:
        OperatorListResponse: Operators sorted by last name, then first name.
    """
    return await service.get_operators(db, establishment, include_inactive)


@router.post("/operators", response_model=OperatorResponse, status_code=201, dependencies=[Depends(require_feature(Feature.OPERATORS))])
async def create_operator(
    payload: OperatorCreate, db: DatabaseSession, establishment: CurrentSite
) -> OperatorResponse:
    """Register a new tablet operator for the current establishment.

    The plain-text PIN is hashed with bcrypt before storage and is never
    returned in any response.

    Args:
        payload (OperatorCreate): Operator profile data and plain-text PIN.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        OperatorResponse: The created operator (PIN hash excluded).
    """
    return await service.create_operator(payload, db, establishment)


@router.patch("/operators/{operator_id}", response_model=OperatorResponse, dependencies=[Depends(require_feature(Feature.OPERATORS))])
async def update_operator(
    operator_id: UUID, payload: OperatorUpdate, db: DatabaseSession, establishment: CurrentSite
) -> OperatorResponse:
    """Partially update an operator's profile.

    Omitting ``pin_code`` leaves the existing PIN hash unchanged.

    Args:
        operator_id (UUID): The operator to update.
        payload (OperatorUpdate): Fields to update.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        OperatorResponse: The updated operator.
    """
    return await service.update_operator(operator_id, payload, db, establishment)


@router.post("/operators/{operator_id}/reset-pin", response_model=OperatorResponse, dependencies=[Depends(require_feature(Feature.OPERATORS))])
async def reset_operator_pin(
    operator_id: UUID, payload: PinResetRequest, db: DatabaseSession, establishment: CurrentSite
) -> OperatorResponse:
    """Replace an operator's tablet PIN.

    Args:
        operator_id (UUID): The operator whose PIN is being reset.
        payload (PinResetRequest): The new plain-text 4-digit PIN.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        OperatorResponse: The updated operator (new PIN hash excluded).
    """
    return await service.reset_pin(operator_id, payload, db, establishment)


@router.delete("/operators/{operator_id}", status_code=204, dependencies=[Depends(require_feature(Feature.OPERATORS))])
async def deactivate_operator(
    operator_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> None:
    """Soft-deactivate an operator without removing their database row.

    Physical deletion is prohibited to preserve historical HACCP signatures
    (temperature records, cleaning logs, reception items) that reference
    this operator.

    Args:
        operator_id (UUID): The operator to deactivate.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
    """
    await service.soft_delete_operator(operator_id, db, establishment)
