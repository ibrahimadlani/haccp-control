"""
FastAPI router for the Non-Conformities domain.

Exposes the NC lifecycle endpoints:

- ``GET  /nonconformities`` — filtered list with status counts.
- ``GET  /nonconformities/stats`` — lightweight status summary widget.
- ``PATCH /nonconformities/{id}/acknowledge`` — operator acknowledges an NC
  (OPEN → IN_PROGRESS).
- ``POST /nonconformities/{id}/corrective-action`` — operator submits a
  corrective action with optional photo (IN_PROGRESS → RESOLVED).
- ``PATCH /nonconformities/{id}/close`` — manager signs off (RESOLVED → CLOSED).

The corrective-action endpoint uses ``Form`` and ``File`` fields instead of
a JSON body to support multipart photo uploads alongside the text description.

S3 is injected via ``Depends(get_s3_service)`` so photo URLs can be built
from stored S3 keys at read time.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.core.s3 import S3Service, get_s3_service
from app.modules.haccp.schemas import ActionCorrectiveResponse
from app.modules.nonconformities import service
from app.modules.nonconformities.models import NonConformityStatus, WorkflowType
from app.modules.nonconformities.schemas import (
    CloseNonConformityRequest,
    NonConformityItemResponse,
    NonConformityListResponse,
    NonConformityStatsResponse,
)

router = APIRouter(
    tags=["Non-Conformities"], dependencies=[Depends(require_feature(Feature.NONCONFORMITIES))]
)


@router.get("/nonconformities", response_model=NonConformityListResponse)
async def list_nonconformities(
    db: DatabaseSession,
    establishment: CurrentSite,
    s3_service: Annotated[S3Service, Depends(get_s3_service)],
    status_filter: Annotated[NonConformityStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[WorkflowType | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> NonConformityListResponse:
    """List non-conformities with optional filters and status counts.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        s3_service: Injected S3 service for photo URL construction.
        status_filter (NonConformityStatus | None): Optional status filter.
        type_filter (WorkflowType | None): Optional workflow type filter.
        limit (int): Max items to return (1–500). Defaults to 100.

    Returns:
        NonConformityListResponse: Filtered NCs with establishment-wide counts.
    """
    return await service.list_nonconformities(
        db, establishment, status_filter, type_filter, limit, s3_service
    )


@router.get("/nonconformities/stats", response_model=NonConformityStatsResponse)
async def get_nonconformity_stats(
    db: DatabaseSession, establishment: CurrentSite
) -> NonConformityStatsResponse:
    """Return lightweight status counts for the NC summary widget.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        NonConformityStatsResponse: Counts by status and latest NC timestamp.
    """
    return await service.get_nonconformity_stats(db, establishment)


@router.patch(
    "/nonconformities/{nonconformity_id}/acknowledge", response_model=NonConformityItemResponse
)
async def acknowledge_nonconformity(
    nonconformity_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
    s3_service: Annotated[S3Service, Depends(get_s3_service)],
) -> NonConformityItemResponse:
    """Acknowledge an open non-conformity (OPEN → IN_PROGRESS).

    Args:
        nonconformity_id (UUID): The NC to acknowledge.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.
        s3_service: Injected S3 service for photo URL construction.

    Returns:
        NonConformityItemResponse: The updated NC detail view.

    Raises:
        HTTPException: 409 Conflict if the NC is not in OPEN status.
    """
    return await service.acknowledge_nonconformity(
        nonconformity_id, db, establishment, operator, s3_service
    )


@router.post(
    "/nonconformities/{nonconformity_id}/corrective-action",
    response_model=ActionCorrectiveResponse,
    status_code=201,
)
async def create_corrective_action(
    nonconformity_id: UUID,
    db: DatabaseSession,
    establishment: CurrentSite,
    operator: CurrentOperator,
    s3_service: Annotated[S3Service, Depends(get_s3_service)],
    description: Annotated[str, Form(min_length=3, max_length=5000)] = "",
    photo: Annotated[UploadFile | None, File()] = None,
) -> ActionCorrectiveResponse:
    """Submit a corrective action with optional photographic evidence (IN_PROGRESS → RESOLVED).

    Uses a multipart form body to support the optional photo upload alongside
    the text description.

    Args:
        nonconformity_id (UUID): The NC to resolve.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        operator (CurrentOperator): The PIN-authenticated operator.
        s3_service: Injected S3 service for photo upload.
        description (str): Corrective action description (3–5000 chars).
        photo (UploadFile | None): Optional JPEG or PNG evidence photo.

    Returns:
        ActionCorrectiveResponse: The created corrective action with photo URL.

    Raises:
        HTTPException: 409 Conflict if the NC is not IN_PROGRESS.
        HTTPException: 400 Bad Request if the photo format is unsupported.
    """
    return await service.create_corrective_action(
        nonconformity_id, db, establishment, operator, s3_service, description, photo
    )


@router.patch("/nonconformities/{nonconformity_id}/close", response_model=NonConformityItemResponse)
async def close_nonconformity(
    nonconformity_id: UUID,
    payload: CloseNonConformityRequest,
    db: DatabaseSession,
    establishment: CurrentSite,
    s3_service: Annotated[S3Service, Depends(get_s3_service)],
) -> NonConformityItemResponse:
    """Manager sign-off: close a resolved non-conformity (RESOLVED → CLOSED).

    Only managers (verified in the service layer via ``ensure_admin_org_access``)
    can close NCs, enforcing the four-eyes principle.

    Args:
        nonconformity_id (UUID): The NC to close.
        payload (CloseNonConformityRequest): Optional closing comment.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        s3_service: Injected S3 service for photo URL construction.

    Returns:
        NonConformityItemResponse: The closed NC detail view.

    Raises:
        HTTPException: 403 Forbidden if the caller lacks manager rights.
        HTTPException: 409 Conflict if the NC is not in RESOLVED status.
    """
    return await service.close_nonconformity(
        nonconformity_id, payload, db, establishment, s3_service
    )
