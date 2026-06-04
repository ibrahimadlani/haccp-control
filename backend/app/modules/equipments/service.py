"""
Business logic for the Equipments domain.

Provides CRUD operations for ``Equipement`` records, all gated behind
``ensure_admin_org_access``.  Soft deletion sets ``deleted_at`` instead of
physically removing the row to preserve FK references from historical
``ReleveTemperature`` records.

Hard deletion is also supported for platform admins only (via
``ensure_platform_admin_access``).  It physically removes the row and
cascades to linked temperature readings — use with care in production.

The ``_build_equipment_response`` helper is a pure function that constructs
the ``EquipmentResponse`` DTO from an ORM instance plus a pre-fetched site
name, avoiding repeated attribute access across list and detail routes.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentEstablishment
from app.modules.equipments.models import Equipement
from app.modules.equipments.schemas import (
    EquipmentCreateRequest,
    EquipmentListResponse,
    EquipmentResponse,
    EquipmentUpdateRequest,
)
from app.modules.personnel.service import ensure_admin_org_access, ensure_platform_admin_access
from app.modules.tenant.models import Etablissement


def _build_equipment_response(equipement: Equipement, site_name: str) -> EquipmentResponse:
    """Build an ``EquipmentResponse`` DTO from an ORM instance and site name.

    Args:
        equipement (Equipement): The ORM instance to convert.
        site_name (str): The display name of the owning establishment,
            denormalised into the response to save a client round-trip.

    Returns:
        EquipmentResponse: The fully populated response DTO.
    """
    return EquipmentResponse(
        id=equipement.id,
        name=equipement.nom,
        equipment_type=equipement.type_equipement,
        min_target_temperature=equipement.temperature_min_cible,
        max_target_temperature=equipement.temperature_max_cible,
        establishment_id=equipement.etablissement_id,
        establishment_site_name=site_name,
        is_active=equipement.deleted_at is None,
    )


async def create_equipment(
    payload: EquipmentCreateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> EquipmentResponse:
    """Create a new piece of temperature-monitored equipment.

    Validates that the target establishment exists within the caller's
    organisation before creating the equipment to enforce multi-tenant scoping.

    Args:
        payload (EquipmentCreateRequest): Validated equipment data including
            the target establishment UUID.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        EquipmentResponse: The created equipment record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the target establishment does not
            exist within the caller's organisation.
    """
    await ensure_admin_org_access(db, establishment)

    site_result = await db.execute(
        select(Etablissement).where(
            Etablissement.id == payload.establishment_id,
            Etablissement.organisation_id == establishment.organisation_id,
            Etablissement.deleted_at.is_(None),
        )
    )
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found in manager scope.",
        )

    equipement = Equipement(
        etablissement_id=payload.establishment_id,
        nom=payload.name,
        type_equipement=payload.equipment_type,
        temperature_min_cible=payload.min_target_temperature,
        temperature_max_cible=payload.max_target_temperature,
    )
    db.add(equipement)
    await db.commit()
    await db.refresh(equipement)
    return _build_equipment_response(equipement, site.nom_site)


async def list_equipment(
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> EquipmentListResponse:
    """Return all active equipment for the locked establishment.

    Joins through ``Etablissement`` to validate the organisation scope and
    eagerly loads the site relationship to avoid N+1 queries when building
    the ``establishment_site_name`` field.

    Args:
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        EquipmentListResponse: Active equipment sorted alphabetically by name.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
    """
    await ensure_admin_org_access(db, establishment)

    equipements_result = await db.execute(
        select(Equipement)
        .join(Etablissement, Etablissement.id == Equipement.etablissement_id)
        .where(
            Etablissement.id == establishment.etablissement_id,
            Etablissement.organisation_id == establishment.organisation_id,
            Etablissement.deleted_at.is_(None),
            Equipement.deleted_at.is_(None),
        )
        .options(selectinload(Equipement.etablissement))
        .order_by(Equipement.nom.asc())
    )
    equipements = equipements_result.scalars().all()

    return EquipmentListResponse(
        items=[
            _build_equipment_response(
                e, e.etablissement.nom_site if e.etablissement is not None else ""
            )
            for e in equipements
        ]
    )


async def update_equipment(
    equipement_id: UUID,
    payload: EquipmentUpdateRequest,
    db: AsyncSession,
    establishment: CurrentEstablishment,
) -> EquipmentResponse:
    """Partially update equipment fields.

    Re-validates the temperature range using the merged (current + new) values
    to catch cases where only one temperature threshold is updated.

    Args:
        equipement_id (UUID): The equipment to update.
        payload (EquipmentUpdateRequest): Fields to update.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.

    Returns:
        EquipmentResponse: The updated equipment record.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 404 Not Found if the equipment is not in scope.
        HTTPException: 422 Unprocessable Entity if the merged temperature
            range is invalid (min >= max).
    """
    await ensure_admin_org_access(db, establishment)

    equipement_result = await db.execute(
        select(Equipement)
        .join(Etablissement, Etablissement.id == Equipement.etablissement_id)
        .where(
            Equipement.id == equipement_id,
            Equipement.deleted_at.is_(None),
            Etablissement.organisation_id == establishment.organisation_id,
            Etablissement.deleted_at.is_(None),
        )
        .options(selectinload(Equipement.etablissement))
    )
    equipement = equipement_result.scalar_one_or_none()
    if equipement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found.")

    # Merge the new thresholds with the existing ones to validate the combined range
    # before applying any changes, preventing partial updates that leave an invalid state.
    next_min: Decimal = payload.min_target_temperature or equipement.temperature_min_cible
    next_max: Decimal = payload.max_target_temperature or equipement.temperature_max_cible
    if next_min >= next_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_target_temperature must be strictly lower than max_target_temperature",
        )

    if payload.name is not None:
        equipement.nom = payload.name
    if payload.equipment_type is not None:
        equipement.type_equipement = payload.equipment_type
    if payload.min_target_temperature is not None:
        equipement.temperature_min_cible = payload.min_target_temperature
    if payload.max_target_temperature is not None:
        equipement.temperature_max_cible = payload.max_target_temperature

    await db.commit()
    await db.refresh(equipement)
    site_name = equipement.etablissement.nom_site if equipement.etablissement is not None else ""
    return _build_equipment_response(equipement, site_name)


async def delete_equipment(
    equipement_id: UUID,
    db: AsyncSession,
    establishment: CurrentEstablishment,
    hard_delete: bool = False,
) -> None:
    """Delete equipment via soft delete (default) or hard delete (platform admin).

    Soft delete sets ``deleted_at`` to hide the equipment from active queries
    while preserving historical ``ReleveTemperature`` FK references.

    Hard delete physically removes the row and cascades to all linked
    temperature records.  It is restricted to platform admins and should
    only be used in non-production cleanup scenarios.

    Args:
        equipement_id (UUID): The equipment to delete.
        db (AsyncSession): The async database session.
        establishment (CurrentEstablishment): The authenticated device context.
        hard_delete (bool): When ``True``, perform a physical delete.
            Defaults to ``False``.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks the required rights.
        HTTPException: 404 Not Found if the equipment is not in scope.
    """
    await ensure_admin_org_access(db, establishment)

    where_clauses = [
        Equipement.id == equipement_id,
        Etablissement.organisation_id == establishment.organisation_id,
        Etablissement.deleted_at.is_(None),
    ]
    if not hard_delete:
        where_clauses.append(Equipement.deleted_at.is_(None))

    equipement_result = await db.execute(
        select(Equipement)
        .join(Etablissement, Etablissement.id == Equipement.etablissement_id)
        .where(*where_clauses)
    )
    equipement = equipement_result.scalar_one_or_none()
    if equipement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found.")

    if hard_delete:
        await ensure_platform_admin_access(db, establishment)
        await db.delete(equipement)
        await db.commit()
        return

    equipement.deleted_at = datetime.now(UTC)
    await db.commit()
