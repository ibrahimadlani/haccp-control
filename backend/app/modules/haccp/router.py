"""
FastAPI router for the HACCP domain.

Exposes endpoints for the two core HACCP data-capture workflows:

1. **Temperature records** — operators submit measured temperatures on the
   shared tablet; out-of-range readings automatically open non-conformity
   tickets.  A bulk endpoint allows submitting a full daily temperature tour
   in a single atomic request.

2. **Time clock** — operators clock in, start/end breaks, and clock out.
   The current status of all operators at an establishment is available for
   the manager supervision dashboard.

All endpoints require a valid establishment JWT (``CurrentSite``).
Temperature and time-clock write operations additionally require the
``CurrentOperator`` dependency (establishment JWT + operator PIN).
"""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentOperator, CurrentSite, DatabaseSession, require_feature
from app.core.features import Feature
from app.modules.haccp import service
from app.modules.haccp.schemas import (
    EstablishmentTimeclockStatusResponse,
    OperatorTimeclockStatusItem,
    PointageCreate,
    PointageResponse,
    TemperatureRecordBulkCreate,
    TemperatureRecordBulkResponse,
    TemperatureRecordCreate,
    TemperatureRecordResponse,
)

router = APIRouter(tags=["HACCP"])


@router.post(
    "/temperature-records",
    response_model=TemperatureRecordResponse,
    status_code=201,
    dependencies=[Depends(require_feature(Feature.HACCP_TEMPERATURE))],
)
async def create_temperature_record(
    payload: TemperatureRecordCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    current_operator: CurrentOperator,
) -> TemperatureRecordResponse:
    """Submit a HACCP temperature measurement.

    Validates the measured value against the equipment's configured thresholds
    and automatically opens a non-conformity ticket when the value is out of range.

    Args:
        payload (TemperatureRecordCreate): Measurement data including equipment ID.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        current_operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        TemperatureRecordResponse: The created record with conformity result
            and linked NC ID (if any).

    Raises:
        HTTPException: 404 Not Found if the equipment is not in scope.
        HTTPException: 422 Unprocessable Entity if ``measured_at`` is outside
            the acceptable recording window (more than 8 h past or 5 min future).
    """
    return await service.create_temperature_record(payload, db, establishment, current_operator)


@router.post(
    "/temperature-records/bulk",
    response_model=TemperatureRecordBulkResponse,
    status_code=201,
    dependencies=[Depends(require_feature(Feature.HACCP_TEMPERATURE))],
)
async def create_temperature_records_bulk(
    payload: TemperatureRecordBulkCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    current_operator: CurrentOperator,
) -> TemperatureRecordBulkResponse:
    """Submit multiple HACCP temperature measurements in a single atomic request.

    Intended for the daily temperature tour: the operator fills in readings for
    all fridges and ovens, then submits everything at once.  Also used by the
    tablet's offline queue to replay buffered measurements after reconnection.

    All equipment IDs are validated before any record is written.  If any ID
    is unknown or belongs to a different establishment, the entire batch is
    rejected with 400.  Any ``measured_at`` outside the 8-hour window is
    rejected with 422 before writing begins.

    Args:
        payload (TemperatureRecordBulkCreate): 1–30 measurements.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        current_operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        TemperatureRecordBulkResponse: All created records with their conformity
            results, a total count, and the number of non-conformities opened.

    Raises:
        HTTPException: 400 Bad Request if any equipment ID is unknown or
            out of scope for this establishment.
        HTTPException: 422 Unprocessable Entity if any ``measured_at`` is outside
            the acceptable recording window.
    """
    return await service.create_temperature_records_bulk(
        payload, db, establishment, current_operator
    )


@router.get("/time-clock-statuses", response_model=EstablishmentTimeclockStatusResponse)
async def get_timeclock_statuses(
    db: DatabaseSession, establishment: CurrentSite
) -> EstablishmentTimeclockStatusResponse:
    """Return the current time-clock status for all operators at the establishment.

    Used by the manager supervision dashboard to display a real-time view
    of who is clocked in, on break, or absent.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.

    Returns:
        EstablishmentTimeclockStatusResponse: One status item per active operator.
    """
    return await service.get_establishment_operator_statuses(db, establishment)


@router.get("/time-clock-statuses/me", response_model=OperatorTimeclockStatusItem)
async def get_my_timeclock_status(
    db: DatabaseSession, establishment: CurrentSite, current_operator: CurrentOperator
) -> OperatorTimeclockStatusItem:
    """Return the current time-clock status for the authenticated operator.

    Called by the tablet after PIN authentication to show the operator their
    current state and the available next actions.

    Args:
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        current_operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        OperatorTimeclockStatusItem: The operator's current status and last event.
    """
    return await service.get_operator_timeclock_status(db, establishment, current_operator)


@router.post(
    "/time-clock-events",
    response_model=PointageResponse,
    status_code=201,
    dependencies=[Depends(require_feature(Feature.TIMECLOCK))],
)
async def create_time_clock_event(
    payload: PointageCreate,
    db: DatabaseSession,
    establishment: CurrentSite,
    current_operator: CurrentOperator,
) -> PointageResponse:
    """Submit a time-clock event (clock in, break, or clock out).

    The service validates that the requested event is a permitted transition
    from the operator's current state before writing.

    Args:
        payload (PointageCreate): The event type to record.
        db (DatabaseSession): Injected async database session.
        establishment (CurrentSite): The authenticated device context.
        current_operator (CurrentOperator): The PIN-authenticated operator.

    Returns:
        PointageResponse: The created time-clock event.

    Raises:
        HTTPException: 403 Forbidden if timeclock is disabled on this site.
        HTTPException: 409 Conflict if the event is not a valid state transition.
    """
    return await service.create_time_clock_event(payload, db, establishment, current_operator)
