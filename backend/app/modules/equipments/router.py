"""
FastAPI router for the Equipments domain.

Exposes CRUD endpoints for temperature-monitored equipment:

- ``GET  /equipments`` — list active equipment for the locked establishment.
  Optionally accepts operator PIN headers to allow tablet-side access without
  manager rights.
- ``POST /equipments`` — create new equipment (manager only).
- ``PATCH /equipments/{equipement_id}`` — update equipment (manager only).
- ``DELETE /equipments/{equipement_id}`` — soft or hard delete (manager/platform admin).

Also proxies two tenant-scoped equipment endpoints used by the admin panel:

- ``GET  /establishments/{etablissement_id}/equipments``
- ``POST /establishments/{etablissement_id}/equipments``
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.api.deps import CurrentSite, DatabaseSession
from app.core.dependencies import get_current_operator
from app.modules.equipments import service
from app.modules.equipments.schemas import (
    EquipmentCreateRequest,
    EquipmentListResponse,
    EquipmentResponse,
    EquipmentUpdateRequest,
)
from app.modules.tenant import service as tenant_service
from app.modules.tenant.schemas import (
    SiteEquipmentCreateRequest,
    SiteEquipmentListResponse,
    SiteEquipmentResponse,
)

router = APIRouter(tags=["Equipments"])


@router.get("/equipments", response_model=EquipmentListResponse)
async def list_equipments(
    db: DatabaseSession,
    establishment: CurrentSite,
    x_device_pin: Annotated[str | None, Header(alias="X-Device-Pin")] = None,
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> EquipmentListResponse:
    """List active equipment for the locked establishment.

    Supports two access modes:
    - **Manager mode** — establishment JWT only (no operator headers).
    - **Operator mode** — establishment JWT plus valid ``X-Device-Pin`` and
      ``X-Operator-Id`` headers, allowing tablet operators to fetch the
      equipment list for the temperature-record form.

    If only one of the two operator headers is provided the request is
    rejected with 401 to prevent partial-header authentication attempts.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        x_device_pin (str | None): Operator's 4-digit PIN (optional).
        x_operator_id (str | None): Operator's UUID (optional).

    Returns:
        EquipmentListResponse: Active equipment sorted by name.

    Raises:
        HTTPException: 401 if only one operator header is supplied.
    """
    if x_device_pin is not None or x_operator_id is not None:
        if not x_device_pin or not x_operator_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Operator headers must include both X-Device-Pin and X-Operator-Id.",
            )
        _ = await get_current_operator(
            x_device_pin=x_device_pin,
            x_operator_id=x_operator_id,
            db=db,
            establishment=establishment,
        )
    return await service.list_equipment(db, establishment)


@router.post("/equipments", response_model=EquipmentResponse, status_code=201)
async def create_equipment(
    payload: EquipmentCreateRequest, db: DatabaseSession, establishment: CurrentSite
) -> EquipmentResponse:
    """Create a new piece of temperature-monitored equipment.

    Args:
        payload (EquipmentCreateRequest): Validated equipment data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        EquipmentResponse: The created equipment record.
    """
    return await service.create_equipment(payload, db, establishment)


@router.patch("/equipments/{equipement_id}", response_model=EquipmentResponse)
async def update_equipment(
    equipement_id: UUID,
    payload: EquipmentUpdateRequest,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> EquipmentResponse:
    """Partially update a piece of equipment.

    Args:
        equipement_id (UUID): The equipment to update.
        payload (EquipmentUpdateRequest): Fields to update.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        EquipmentResponse: The updated equipment record.
    """
    return await service.update_equipment(equipement_id, payload, db, establishment)


@router.delete("/equipments/{equipement_id}", status_code=204)
async def delete_equipment(
    equipement_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    hard_delete: bool = Query(default=False),
) -> None:
    """Delete equipment (soft by default, hard for platform admins).

    Args:
        equipement_id (UUID): The equipment to delete.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        hard_delete (bool): Physical delete when ``True``. Requires platform-admin rights.
    """
    return await service.delete_equipment(equipement_id, db, establishment, hard_delete=hard_delete)


@router.get(
    "/establishments/{etablissement_id}/equipments", response_model=SiteEquipmentListResponse
)
async def list_establishment_equipment(
    etablissement_id: UUID, db: DatabaseSession, establishment: CurrentSite
) -> SiteEquipmentListResponse:
    """List equipment for a specific establishment (admin panel view).

    Args:
        etablissement_id (UUID): Target establishment primary key.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SiteEquipmentListResponse: Active equipment sorted by name.
    """
    return await tenant_service.list_site_equipment(etablissement_id, db, establishment)


@router.post(
    "/establishments/{etablissement_id}/equipments",
    response_model=SiteEquipmentResponse,
    status_code=201,
)
async def create_establishment_equipment(
    etablissement_id: UUID,
    payload: SiteEquipmentCreateRequest,
    db: DatabaseSession,
    establishment: CurrentSite,
) -> SiteEquipmentResponse:
    """Add equipment to a specific establishment (admin panel view).

    Args:
        etablissement_id (UUID): Target establishment primary key.
        payload (SiteEquipmentCreateRequest): Validated equipment data.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        SiteEquipmentResponse: The created equipment record.
    """
    return await tenant_service.create_site_equipment(etablissement_id, payload, db, establishment)
