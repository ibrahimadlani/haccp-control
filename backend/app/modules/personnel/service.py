"""
Business logic for the Personnel domain.

This module provides two distinct service layers:

1. **User management** — CRUD operations for ``Utilisateur`` records and their
   ``AffectationSite`` assignments.  All mutations require the caller to hold
   manager-level rights on the organisation (enforced by ``ensure_admin_org_access``).

2. **Operator management** — CRUD operations for ``Operator`` records used on
   shared tablets.  PIN values are hashed with bcrypt before storage and are
   never returned in any response.

The access-guard functions ``ensure_admin_org_access`` and
``ensure_platform_admin_access`` are also exported for use by other modules
(catalog, equipments, tenant) that share the same authorisation rules.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentEstablishment
from app.core.role_utils import is_manager_role, is_platform_admin_role
from app.core.security import get_password_hash
from app.modules.personnel.models import AffectationSite, Operator, Role, Utilisateur
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
    UserSiteSummary,
    UserUpdateRequest,
)
from app.modules.tenant.models import Etablissement

# ---------------------------------------------------------------------------
# Access guards — imported and reused by catalog, equipments, tenant modules
# ---------------------------------------------------------------------------


async def ensure_admin_org_access(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Assert that the JWT holder has manager-level rights on the current organisation.

    Looks up all active ``AffectationSite`` rows for the ``manager_user_id``
    embedded in the establishment JWT, then checks whether any of those
    assignments belongs to the same organisation and carries a manager role.

    This guard is the application's Row-Level Security boundary for all
    write operations that span multiple establishments within an organisation.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context
            carrying the ``manager_user_id`` to validate.

    Raises:
        HTTPException: 403 Forbidden if no active manager assignment is found for
            the current organisation.
    """
    manager_assignment_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.role), selectinload(AffectationSite.etablissement))
        .where(
            AffectationSite.utilisateur_id == establishment.manager_user_id,
            AffectationSite.etablissement_id == establishment.etablissement_id,
            AffectationSite.is_active.is_(True),
        )
    )
    manager_assignments = manager_assignment_result.scalars().all()

    has_org_admin_rights = any(
        a.etablissement is not None
        and a.etablissement.organisation_id == establishment.organisation_id
        and a.role is not None
        and is_manager_role(a.role)
        for a in manager_assignments
    )
    if not has_org_admin_rights:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this organisation.",
        )


async def ensure_platform_admin_access(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Assert that the JWT holder has platform-administrator grade permissions.

    Stricter than ``ensure_admin_org_access``: the caller must hold a role
    whose ``is_platform_admin_role`` check returns ``True``.  Used exclusively
    to gate irreversible operations such as hard-deletes.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 403 Forbidden if the caller is not a platform administrator.
    """
    manager_assignment_result = await db.execute(
        select(AffectationSite)
        .options(selectinload(AffectationSite.role), selectinload(AffectationSite.etablissement))
        .where(
            AffectationSite.utilisateur_id == establishment.manager_user_id,
            AffectationSite.is_active.is_(True),
        )
    )
    manager_assignments = manager_assignment_result.scalars().all()

    has_platform_admin_rights = any(
        a.etablissement is not None
        and a.etablissement.organisation_id == establishment.organisation_id
        and a.role is not None
        and is_platform_admin_role(a.role)
        for a in manager_assignments
    )
    if not has_platform_admin_rights:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hard delete is restricted to platform administrators.",
        )


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


async def list_roles(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[RoleListItemResponse]:
    """Return all available roles ordered alphabetically.

    Roles are global (not scoped to an organisation), so no tenant filter is
    applied here.  Access is still gated by manager rights to prevent operators
    from listing roles and crafting privilege-escalation payloads.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        list[RoleListItemResponse]: All roles sorted by name.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)
    roles_result = await db.execute(select(Role).order_by(Role.nom_role.asc()))
    roles = roles_result.scalars().all()
    return [RoleListItemResponse(id=role.id, role_name=role.nom_role) for role in roles]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def _build_deduplicated_sites(assignments: list[AffectationSite]) -> dict[UUID, UserSiteSummary]:
    """Build a deduplicated mapping of establishment ID → site summary.

    A user may have multiple ``AffectationSite`` rows for the same establishment
    (one per role).  This helper collapses them to one entry per site so the API
    response does not repeat the same site in the ``sites`` list.

    Args:
        assignments (list[AffectationSite]): The user's assignments for a given
            organisation, with ``etablissement`` eagerly loaded.

    Returns:
        dict[UUID, UserSiteSummary]: Mapping keyed by ``etablissement_id``.
    """
    return {
        a.etablissement_id: UserSiteSummary(
            establishment_id=a.etablissement_id,
            site_name=a.etablissement.nom_site,
        )
        for a in assignments
        if a.etablissement is not None
    }


async def list_users(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> list[UserListItemResponse]:
    """Return all non-deleted collaborators assigned within the current organisation.

    The query joins through ``AffectationSite`` and ``Etablissement`` to filter
    by ``organisation_id``, ensuring strict multi-tenant isolation: a manager of
    organisation A cannot see users of organisation B even if they share
    establishment IDs.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        list[UserListItemResponse]: All collaborators sorted by last name, then
            first name.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)

    users_result = await db.execute(
        select(Utilisateur)
        .join(AffectationSite, AffectationSite.utilisateur_id == Utilisateur.id)
        .join(Etablissement, Etablissement.id == AffectationSite.etablissement_id)
        .where(
            Utilisateur.deleted_at.is_(None),
            Etablissement.organisation_id == establishment.organisation_id,
        )
        .options(
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.role),
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.etablissement),
        )
        .order_by(Utilisateur.nom.asc(), Utilisateur.prenom.asc())
        .distinct()
    )
    users = users_result.scalars().all()

    rows: list[UserListItemResponse] = []
    for user in users:
        # Filter assignments to the current organisation in Python rather than
        # adding a second JOIN level, because the assignments are already eagerly
        # loaded and the extra DB round-trip would outweigh any benefit.
        org_assignments = [
            a
            for a in user.affectations
            if a.etablissement is not None
            and a.etablissement.organisation_id == establishment.organisation_id
        ]
        if not org_assignments:
            continue
        primary = org_assignments[0]
        role_name = primary.role.nom_role if primary.role is not None else "OPERATEUR"
        deduped_sites = _build_deduplicated_sites(org_assignments)
        rows.append(
            UserListItemResponse(
                id=user.id,
                last_name=user.nom,
                first_name=user.prenom,
                email=user.email,
                role_id=primary.role_id,
                role_name=role_name,
                is_active=any(a.is_active for a in org_assignments),
                sites=list(deduped_sites.values()),
            )
        )
    return rows


async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> UserCreateResponse:
    """Create a new collaborator and assign them atomically to one or more establishments.

    All validations (role existence, email uniqueness, establishment ownership)
    are performed before the ``Utilisateur`` row is written to guarantee a clean
    failure mode with no partial state.

    Args:
        payload (UserCreateRequest): The validated creation payload including
            plain-text password and PIN.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        UserCreateResponse: The new user's ID, email, and assigned establishment IDs.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the requested role does not exist.
        HTTPException: 400 Bad Request if the email is already taken or an
            establishment ID belongs to a different organisation.
    """
    await ensure_admin_org_access(db, establishment)

    role_result = await db.execute(select(Role).where(Role.id == payload.role_id))
    if role_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    existing_user_result = await db.execute(
        select(Utilisateur).where(
            Utilisateur.email == payload.email, Utilisateur.deleted_at.is_(None)
        )
    )
    if existing_user_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already used.")

    sites_result = await db.execute(
        select(Etablissement).where(
            Etablissement.id.in_(payload.establishment_ids),
            Etablissement.organisation_id == establishment.organisation_id,
            Etablissement.deleted_at.is_(None),
        )
    )
    sites = sites_result.scalars().all()
    if set(payload.establishment_ids) != {site.id for site in sites}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid establishments."
        )

    user = Utilisateur(
        nom=payload.last_name,
        prenom=payload.first_name,
        email=str(payload.email),
        # bcrypt hashing happens here in the service layer, never at the schema level.
        mot_de_passe_hash=get_password_hash(payload.password),
        code_pin=get_password_hash(payload.pin_code),
    )
    db.add(user)
    # Flush to obtain the generated UUID before creating the assignments.
    await db.flush()

    for etablissement_id in payload.establishment_ids:
        db.add(
            AffectationSite(
                utilisateur_id=user.id,
                etablissement_id=etablissement_id,
                role_id=payload.role_id,
                is_active=True,
            )
        )

    await db.commit()
    return UserCreateResponse(
        user_id=user.id, email=user.email, establishment_ids=payload.establishment_ids
    )


async def update_user(
    utilisateur_id: UUID,
    payload: UserUpdateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> UserListItemResponse:
    """Partially update a collaborator's profile and optionally reassign establishments.

    When ``role_id`` or ``establishment_ids`` is supplied, the existing
    ``AffectationSite`` rows for this organisation are deleted and rebuilt
    atomically.  This delete-then-insert approach is intentional: it avoids the
    complexity of detecting which rows to add, update, or remove individually,
    and the cascade delete constraint prevents orphaned assignments.

    Args:
        utilisateur_id (UUID): The ``Utilisateur`` to update.
        payload (UserUpdateRequest): Partial update payload (PATCH semantics).
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        UserListItemResponse: The updated collaborator's full profile.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the user or role does not exist.
        HTTPException: 400 Bad Request if the email is already taken or an
            establishment ID is invalid.
    """
    await ensure_admin_org_access(db, establishment)

    user_result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == utilisateur_id, Utilisateur.deleted_at.is_(None))
        .options(
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.role),
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.etablissement),
        )
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    org_assignments = [
        a
        for a in user.affectations
        if a.etablissement is not None
        and a.etablissement.organisation_id == establishment.organisation_id
    ]
    if not org_assignments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.email is not None and payload.email != user.email:
        dup = await db.execute(
            select(Utilisateur).where(
                Utilisateur.email == payload.email,
                Utilisateur.deleted_at.is_(None),
                Utilisateur.id != user.id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already used."
            )
        user.email = str(payload.email)

    if payload.last_name is not None:
        user.nom = payload.last_name
    if payload.first_name is not None:
        user.prenom = payload.first_name
    if payload.password is not None:
        user.mot_de_passe_hash = get_password_hash(payload.password)
    if payload.pin_code is not None:
        user.code_pin = get_password_hash(payload.pin_code)

    next_role_id = payload.role_id or org_assignments[0].role_id
    if payload.role_id is not None:
        role_result = await db.execute(select(Role).where(Role.id == payload.role_id))
        if role_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    next_site_ids = (
        set(payload.establishment_ids)
        if payload.establishment_ids is not None
        else {a.etablissement_id for a in org_assignments}
    )

    if payload.establishment_ids is not None:
        sites_result = await db.execute(
            select(Etablissement).where(
                Etablissement.id.in_(payload.establishment_ids),
                Etablissement.organisation_id == establishment.organisation_id,
                Etablissement.deleted_at.is_(None),
            )
        )
        if next_site_ids != {s.id for s in sites_result.scalars().all()}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid establishments."
            )

    should_rebuild = payload.role_id is not None or payload.establishment_ids is not None
    if should_rebuild:
        # Preserve the active state from the payload, or carry forward the
        # current state when is_active was not supplied in this request.
        assignment_is_active = (
            payload.is_active
            if payload.is_active is not None
            else any(a.is_active for a in org_assignments)
        )
        for a in org_assignments:
            await db.delete(a)
        await db.flush()
        for etablissement_id in next_site_ids:
            db.add(
                AffectationSite(
                    utilisateur_id=user.id,
                    etablissement_id=etablissement_id,
                    role_id=next_role_id,
                    is_active=assignment_is_active,
                )
            )
    elif payload.is_active is not None:
        for a in org_assignments:
            a.is_active = payload.is_active

    await db.commit()

    # Re-query after commit to return a fully consistent, post-update state.
    refreshed_result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == user.id)
        .options(
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.role),
            selectinload(Utilisateur.affectations).selectinload(AffectationSite.etablissement),
        )
    )
    refreshed_user = refreshed_result.scalar_one()
    refreshed_assignments = [
        a
        for a in refreshed_user.affectations
        if a.etablissement is not None
        and a.etablissement.organisation_id == establishment.organisation_id
    ]
    primary = refreshed_assignments[0]
    deduped_sites = _build_deduplicated_sites(refreshed_assignments)

    return UserListItemResponse(
        id=refreshed_user.id,
        last_name=refreshed_user.nom,
        first_name=refreshed_user.prenom,
        email=refreshed_user.email,
        role_id=primary.role_id,
        role_name=primary.role.nom_role if primary.role else "OPERATEUR",
        is_active=any(a.is_active for a in refreshed_assignments),
        sites=list(deduped_sites.values()),
    )


async def delete_user(
    utilisateur_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    hard_delete: bool = False,
) -> None:
    """Delete a collaborator via soft delete (default) or hard delete (platform admin only).

    Soft delete sets ``deleted_at`` on the ``Utilisateur`` row and marks all
    organisation-scoped assignments inactive, preserving historical data required
    for HACCP audit trails (e.g. who recorded a temperature measurement).

    Hard delete physically removes the row and is restricted to platform admins.
    It is blocked if the user is assigned to establishments outside the caller's
    organisation to prevent accidental cross-tenant data loss.

    Args:
        utilisateur_id (UUID): The ``Utilisateur`` to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        hard_delete (bool): When ``True``, physically deletes the row. Defaults
            to ``False`` (soft delete).

    Raises:
        HTTPException: 403 Forbidden if the caller lacks the required rights.
        HTTPException: 404 Not Found if the user does not exist or is not
            assigned within the caller's organisation.
        HTTPException: 409 Conflict if a hard delete is attempted on a user
            who also belongs to another organisation.
    """
    await ensure_admin_org_access(db, establishment)

    user_result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == utilisateur_id)
        .options(selectinload(Utilisateur.affectations).selectinload(AffectationSite.etablissement))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    org_assignments = [
        a
        for a in user.affectations
        if a.etablissement is not None
        and a.etablissement.organisation_id == establishment.organisation_id
    ]
    if not org_assignments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if hard_delete:
        await ensure_platform_admin_access(db, establishment)
        # Safety check: if the user is also assigned to other organisations, a
        # hard delete would silently remove data for those tenants too.
        outside = [
            a
            for a in user.affectations
            if a.etablissement is not None
            and a.etablissement.organisation_id != establishment.organisation_id
        ]
        if outside:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot hard delete user assigned outside org.",
            )
        await db.delete(user)
        await db.commit()
        return

    # Soft delete: preserve the row for HACCP audit trail integrity.
    user.deleted_at = datetime.now(UTC)
    for a in org_assignments:
        a.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Operators (tablet PIN CRUD)
# ---------------------------------------------------------------------------


async def get_operators(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    include_inactive: bool = False,
) -> OperatorListResponse:
    """Return operators registered for the current establishment.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.
        include_inactive (bool): When ``True``, also returns soft-deleted operators.
            Defaults to ``False``.

    Returns:
        OperatorListResponse: Paginated list of operators sorted by last name,
            then first name.
    """
    where = [Operator.establishment_id == establishment.etablissement_id]
    if not include_inactive:
        where.append(Operator.is_active.is_(True))

    result = await db.execute(
        select(Operator).where(*where).order_by(Operator.last_name, Operator.first_name)
    )
    operators = result.scalars().all()
    return OperatorListResponse(
        items=[OperatorResponse.model_validate(op) for op in operators],
        total=len(operators),
    )


async def create_operator(
    payload: OperatorCreate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> OperatorResponse:
    """Register a new kitchen operator for the current establishment.

    The raw PIN from ``payload.pin_code`` is hashed with bcrypt before
    persistence.  The hash is the only form ever written to the database.

    Args:
        payload (OperatorCreate): Validated creation payload including plain PIN.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        OperatorResponse: The created operator (PIN hash excluded).
    """
    operator = Operator(
        establishment_id=establishment.etablissement_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        pin_hash=get_password_hash(payload.pin_code),
        hygiene_training_date=payload.hygiene_training_date,
        medical_check_date=payload.medical_check_date,
    )
    db.add(operator)
    await db.commit()
    await db.refresh(operator)
    return OperatorResponse.model_validate(operator)


async def update_operator(
    operator_id: UUID,
    payload: OperatorUpdate,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> OperatorResponse:
    """Partially update an operator's profile.

    PIN is only rehashed when ``pin_code`` is explicitly provided.  Omitting the
    field leaves the existing hash untouched.

    Args:
        operator_id (UUID): The operator to update.
        payload (OperatorUpdate): Partial update payload.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        OperatorResponse: The updated operator.

    Raises:
        HTTPException: 404 Not Found if the operator does not exist or is inactive.
    """
    operator = await _get_active_operator(db, establishment, operator_id)
    update_data = payload.model_dump(exclude_unset=True)
    # Extract pin_code before the generic field loop to avoid setting the raw
    # value on the model — it must be hashed first.
    pin_code = update_data.pop("pin_code", None)
    for field, value in update_data.items():
        setattr(operator, field, value)
    if pin_code is not None:
        operator.pin_hash = get_password_hash(pin_code)
    await db.commit()
    await db.refresh(operator)
    return OperatorResponse.model_validate(operator)


async def reset_pin(
    operator_id: UUID,
    payload: PinResetRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> OperatorResponse:
    """Replace an operator's PIN with a new one.

    Dedicated endpoint to isolate PIN reset logic from general profile updates,
    enabling fine-grained audit logging and separate permission checks in future.

    Args:
        operator_id (UUID): The operator whose PIN is being reset.
        payload (PinResetRequest): The new 4-digit PIN in plain text.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Returns:
        OperatorResponse: The updated operator (new PIN hash excluded).

    Raises:
        HTTPException: 404 Not Found if the operator does not exist or is inactive.
    """
    operator = await _get_active_operator(db, establishment, operator_id)
    operator.pin_hash = get_password_hash(payload.pin_code)
    await db.commit()
    await db.refresh(operator)
    return OperatorResponse.model_validate(operator)


async def soft_delete_operator(
    operator_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> None:
    """Deactivate an operator without removing the database row.

    Physical deletion is prohibited because the operator's ID is referenced by
    historical HACCP signatures (temperature records, cleaning logs, reception
    items).  Soft deletion preserves those audit trails.

    Args:
        operator_id (UUID): The operator to deactivate.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context.

    Raises:
        HTTPException: 404 Not Found if the operator does not exist or is already
            inactive.
    """
    operator = await _get_active_operator(db, establishment, operator_id)
    # is_active = False is the only permitted deletion strategy for operators.
    operator.is_active = False
    await db.commit()


async def _get_active_operator(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    operator_id: UUID,
) -> Operator:
    """Load an active operator scoped to the current establishment.

    Combines the primary-key lookup, the multi-tenant establishment filter, and
    the soft-delete filter in a single query to avoid N+1 patterns.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated establishment context
            used to enforce tenant isolation.
        operator_id (UUID): The operator's primary key.

    Returns:
        Operator: The matching active operator ORM instance.

    Raises:
        HTTPException: 404 Not Found if no active operator with that ID exists in
            the current establishment.
    """
    result = await db.execute(
        select(Operator).where(
            Operator.id == operator_id,
            Operator.establishment_id == establishment.etablissement_id,
            Operator.is_active.is_(True),
        )
    )
    operator = result.scalar_one_or_none()
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Opérateur introuvable ou inactif."
        )
    return operator
