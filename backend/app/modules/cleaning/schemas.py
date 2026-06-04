"""
Pydantic schemas for the Cleaning (Nettoyage) domain.

Covers three groups of schemas:

1. **Configuration** — ``CleaningZoneCreate/Response``,
   ``CleaningRoutineCreate/Response``, and
   ``CleaningTaskTemplateCreate/Response`` for building and managing the
   cleaning plan.

2. **Todo view** — ``RoutineTodoResponse``, ``ZoneTodoItem``, and
   ``TaskTodoItem`` compose the nested routine-detail view served to the
   tablet.  Each task carries the latest log for today (if any) so the
   operator can see at a glance what has already been done.

3. **Execution** — ``CleaningLogItem`` and ``BulkCleaningLogCreate`` let
   the tablet submit multiple task completions in a single request.
   ``CleaningLogItem`` enforces that a comment is required when the status
   is ``ISSUE``.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.cleaning.models import CleaningStatus, ScheduleType


class CleaningZoneCreate(BaseModel):
    """Request body for creating a cleaning zone.

    Attributes:
        name (str): Zone display name (1–255 chars).
    """

    name: str = Field(min_length=1, max_length=255)


class CleaningZoneResponse(BaseModel):
    """Response body for a cleaning zone.

    Attributes:
        id (UUID): Zone primary key.
        establishment_id (UUID): Owning establishment.
        name (str): Zone display name.
    """

    model_config = {"from_attributes": True}
    id: UUID
    establishment_id: UUID
    name: str


class CleaningZoneListResponse(BaseModel):
    """Wrapper response for the cleaning zone list endpoint.

    Attributes:
        items (list[CleaningZoneResponse]): Zones sorted by name.
    """

    items: list[CleaningZoneResponse]


class CleaningRoutineCreate(BaseModel):
    """Request body for creating a cleaning routine.

    Attributes:
        name (str): Routine display name (1–255 chars).
        schedule_type (ScheduleType): When this routine is expected to run.
    """

    name: str = Field(min_length=1, max_length=255)
    schedule_type: ScheduleType


class CleaningRoutineResponse(BaseModel):
    """Response body for a cleaning routine.

    Attributes:
        id (UUID): Routine primary key.
        establishment_id (UUID): Owning establishment.
        name (str): Routine display name.
        schedule_type (ScheduleType): Schedule classification.
    """

    model_config = {"from_attributes": True}
    id: UUID
    establishment_id: UUID
    name: str
    schedule_type: ScheduleType


class CleaningRoutineListResponse(BaseModel):
    """Wrapper response for the cleaning routine list endpoint.

    Attributes:
        items (list[CleaningRoutineResponse]): Routines sorted by name.
    """

    items: list[CleaningRoutineResponse]


class CleaningTaskTemplateCreate(BaseModel):
    """Request body for adding a task template to a routine.

    Attributes:
        zone_id (UUID): The zone this task belongs to.
        name (str): Task display name (1–255 chars).
        description (str | None): Optional detailed instructions.
    """

    zone_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CleaningTaskTemplateResponse(BaseModel):
    """Response body for a cleaning task template.

    Attributes:
        id (UUID): Task template primary key.
        routine_id (UUID): Owning routine.
        zone_id (UUID): Associated zone.
        name (str): Task display name.
        description (str | None): Optional instructions.
    """

    model_config = {"from_attributes": True}
    id: UUID
    routine_id: UUID
    zone_id: UUID
    name: str
    description: str | None


class CleaningLogResponse(BaseModel):
    """Response body for a single cleaning log entry.

    Attributes:
        id (UUID): Log entry primary key.
        task_id (UUID): Executed task template.
        operator_id (UUID): Operator who executed the task.
        status (CleaningStatus): Reported outcome (DONE or ISSUE).
        comment (str | None): Issue description.
        executed_at (datetime): Site-local timestamp of execution.
    """

    model_config = {"from_attributes": True}
    id: UUID
    task_id: UUID
    operator_id: UUID
    status: CleaningStatus
    comment: str | None
    executed_at: datetime


class TaskTodoItem(BaseModel):
    """One task in the routine todo-list view.

    Carries the latest ``CleaningLog`` for today (if any) so the tablet can
    display each task's completion status without a separate fetch.

    Attributes:
        task_id (UUID): Task template primary key.
        name (str): Task display name.
        description (str | None): Optional instructions.
        log (CleaningLogResponse | None): Today's latest log for this task,
            or ``None`` if the task has not yet been executed today.
    """

    task_id: UUID
    name: str
    description: str | None
    log: CleaningLogResponse | None = None


class ZoneTodoItem(BaseModel):
    """One zone in the routine todo-list view, grouping its tasks.

    Attributes:
        zone_id (UUID): Zone primary key.
        zone_name (str): Zone display name.
        tasks (list[TaskTodoItem]): Tasks belonging to this zone.
    """

    zone_id: UUID
    zone_name: str
    tasks: list[TaskTodoItem]

    @property
    def is_complete(self) -> bool:
        """Return ``True`` when all tasks in this zone have a log entry for today."""
        return bool(self.tasks) and all(t.log is not None for t in self.tasks)


class RoutineTodoResponse(BaseModel):
    """Full todo-list view for a cleaning routine.

    Returned by both the current-routine and routine-detail endpoints.
    Zones are sorted alphabetically; tasks within each zone are sorted by
    zone then by name in the service layer.

    Attributes:
        routine_id (UUID): Routine primary key.
        routine_name (str): Routine display name.
        schedule_type (ScheduleType): Schedule classification.
        zones (list[ZoneTodoItem]): Zones with their tasks and today's logs.
    """

    routine_id: UUID
    routine_name: str
    schedule_type: ScheduleType
    zones: list[ZoneTodoItem]


class CleaningLogItem(BaseModel):
    """One task completion entry within a bulk log submission.

    Attributes:
        task_id (UUID): The task that was executed.
        status (CleaningStatus): Reported outcome.
        comment (str | None): Required when ``status`` is ``ISSUE``.
    """

    task_id: UUID
    status: CleaningStatus
    comment: str | None = None

    @model_validator(mode="after")
    def comment_required_for_issue(self) -> "CleaningLogItem":
        """Enforce that a comment is provided when reporting an issue.

        Returns:
            CleaningLogItem: The validated model instance.

        Raises:
            ValueError: If ``status == ISSUE`` and no comment is provided.
        """
        if self.status == CleaningStatus.ISSUE and not self.comment:
            raise ValueError("Un commentaire est obligatoire lorsque le statut est ISSUE.")
        return self


class BulkCleaningLogCreate(BaseModel):
    """Request body for submitting multiple task completions in a single request.

    Allows the tablet to send the entire routine execution in one call at the
    end of a cleaning session, reducing network round-trips.

    Attributes:
        items (list[CleaningLogItem]): At least one task completion entry.
    """

    items: list[CleaningLogItem] = Field(min_length=1)


class BulkCleaningLogResponse(BaseModel):
    """Response returned after a successful bulk log creation.

    Attributes:
        created (list[CleaningLogResponse]): All created log entries.
        count (int): Total number of entries created.
    """

    created: list[CleaningLogResponse]
    count: int
