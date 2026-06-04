"""
Pydantic schemas for the Non-Conformities domain.

Covers three response types:

1. ``NonConformityItemResponse`` — the rich single-item view that aggregates
   the NC ticket, its source temperature record (equipment, measured value,
   deviation), and its corrective action (description, photo URL) into one
   flat payload.  This avoids multiple client round-trips on the dashboard.

2. ``NonConformityListResponse`` — wraps a list of items with status
   counters (open, in-progress, resolved, closed) for the dashboard summary
   bar.

3. ``NonConformityStatsResponse`` — a lightweight statistics payload for
   the summary widget, avoiding a full item list fetch when only counts are
   needed.

``CloseNonConformityRequest`` carries the optional manager comment written
at closure.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.modules.haccp.models import SourceReleve
from app.modules.nonconformities.models import NonConformityStatus, WorkflowType


class NonConformityItemResponse(BaseModel):
    """Full detail view for one non-conformity ticket.

    Aggregates data from the ``NonConformity``, ``ReleveTemperature``,
    ``Equipement``, and ``ActionCorrective`` tables into a single flat
    response to minimise client round-trips.

    Attributes:
        id (UUID): NC ticket primary key.
        workflow_type (WorkflowType): TEMPERATURE or RECEPTION.
        status (NonConformityStatus): Current lifecycle status.
        opened_by_name (str): Pre-formatted name of the operator who opened the NC.
        opened_at (datetime): When the NC was opened.
        assigned_to_name (str | None): Name of the acknowledging operator.
        assigned_at (datetime | None): When the NC was acknowledged.
        resolved_at (datetime | None): When the corrective action was submitted.
        closed_by_name (str | None): Name of the manager who closed the NC.
        closed_at (datetime | None): When the NC was closed.
        closing_comment (str | None): Manager's closing note.
        source_record_id (UUID | None): FK to the offending temperature record.
        equipment_id (UUID | None): Equipment that triggered the NC.
        equipment_name (str | None): Equipment display name.
        measured_value (Decimal | None): The out-of-range temperature value.
        temperature_min (Decimal | None): Equipment lower threshold at the time
            of the measurement.
        temperature_max (Decimal | None): Equipment upper threshold.
        deviation_celsius (Decimal | None): How far outside the threshold the
            reading was (always positive).
        source (SourceReleve | None): Whether the reading was manual or IoT.
        corrective_action_id (UUID | None): Corrective action primary key.
        corrective_action_description (str | None): Free-text description.
        corrective_action_signed_at (datetime | None): When the action was signed.
        corrective_action_photo_url (str | None): Public URL for the evidence
            photo, constructed from the S3 key at read time.
    """

    id: UUID
    workflow_type: WorkflowType
    status: NonConformityStatus
    opened_by_name: str
    opened_at: datetime
    assigned_to_name: str | None
    assigned_at: datetime | None
    resolved_at: datetime | None
    closed_by_name: str | None
    closed_at: datetime | None
    closing_comment: str | None
    source_record_id: UUID | None
    equipment_id: UUID | None
    equipment_name: str | None
    measured_value: Decimal | None
    temperature_min: Decimal | None
    temperature_max: Decimal | None
    deviation_celsius: Decimal | None
    source: SourceReleve | None
    corrective_action_id: UUID | None
    corrective_action_description: str | None
    corrective_action_signed_at: datetime | None
    corrective_action_photo_url: str | None


class NonConformityListResponse(BaseModel):
    """List response for non-conformities with status counters.

    The status counters cover all NCs in the establishment (not just the
    current page), allowing the dashboard summary bar to display accurate
    totals regardless of applied filters or pagination.

    Attributes:
        items (list[NonConformityItemResponse]): NC records (filtered and limited).
        total_open (int): Total open NCs in the establishment.
        total_in_progress (int): Total in-progress NCs.
        total_resolved (int): Total resolved NCs awaiting closure.
        total_closed (int): Total closed NCs.
    """

    items: list[NonConformityItemResponse]
    total_open: int
    total_in_progress: int
    total_resolved: int
    total_closed: int


class NonConformityStatsResponse(BaseModel):
    """Lightweight statistics summary for the NC dashboard widget.

    Attributes:
        total (int): Total NC count across all statuses.
        total_open (int): Open NCs.
        total_in_progress (int): In-progress NCs.
        total_resolved (int): Resolved NCs awaiting manager sign-off.
        total_closed (int): Closed NCs.
        latest_at (datetime | None): Timestamp of the most recently opened NC,
            or ``None`` if no NCs exist.
    """

    total: int
    total_open: int
    total_in_progress: int
    total_resolved: int
    total_closed: int
    latest_at: datetime | None


class CloseNonConformityRequest(BaseModel):
    """Request body for the manager close-NC endpoint.

    Attributes:
        closing_comment (str | None): Optional manager note written at closure.
            Stored on the ``NonConformity`` row for the audit trail.
    """

    closing_comment: str | None = None
