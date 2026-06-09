"""
ORM models for the Cleaning (Nettoyage) domain.

This module defines the four entities that model the cleaning plan and its
execution log:

- ``CleaningZone`` — a named area of the kitchen (e.g. "Cuisine chaude",
  "Chambre froide") to which cleaning tasks are assigned.

- ``CleaningRoutine`` — a named cleaning schedule (e.g. "Ouverture",
  "Fermeture") that groups a set of task templates and is associated with a
  ``ScheduleType`` to allow automatic selection based on the time of day.

- ``CleaningTaskTemplate`` — a reusable task definition within a routine,
  describing what must be cleaned in which zone.

- ``CleaningLog`` — the execution record created when an operator marks a
  task as ``DONE`` or ``ISSUE``.  A comment is mandatory when the status is
  ``ISSUE`` to capture the nature of the problem for the HACCP audit trail.

Relationships are designed so that the tablet can fetch the full routine
structure in a single query, while logs are queried separately per session
to keep the payload size predictable.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class ScheduleType(StrEnum):
    """When a cleaning routine is expected to be executed.

    Used by :func:`~app.modules.cleaning.service._infer_schedule_type` to
    automatically select the appropriate routine based on the current site-local
    time when the tablet operator requests the "current routine".

    Attributes:
        OPENING: Morning opening tasks (before 13:00 local time).
        CLOSING: Evening closing tasks (13:00 or later local time).
        WEEKLY: Weekly deep-clean tasks (manually selected).
        MONTHLY: Monthly deep-clean tasks (manually selected).
    """

    OPENING = "OPENING"
    CLOSING = "CLOSING"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class CleaningStatus(StrEnum):
    """Outcome reported by the operator when executing a cleaning task.

    Attributes:
        DONE: Task completed successfully without issue.
        ISSUE: Task completed but a problem was observed. A comment is
            mandatory when this status is used to describe the issue.
    """

    DONE = "DONE"
    ISSUE = "ISSUE"


class CleaningZone(TimestampMixin, Base):
    """A named kitchen area to which cleaning task templates are assigned.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment.
        name (str): Zone display name (e.g. "Cuisine chaude", "Plonge").
        task_templates (list[CleaningTaskTemplate]): Task templates in this zone.
    """

    __tablename__ = "cleaning_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    task_templates: Mapped[list[CleaningTaskTemplate]] = relationship(
        "CleaningTaskTemplate", back_populates="zone", cascade="all, delete-orphan", lazy="noload"
    )


class CleaningRoutine(TimestampMixin, Base):
    """A named cleaning schedule grouping task templates by time-of-day type.

    Each establishment should have at least one routine per ``ScheduleType``
    it uses.  When no matching routine is found for the requested type, the
    service falls back to the oldest routine to avoid returning a 404 on a
    tablet that has no configured schedule.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment.
        name (str): Routine display name (e.g. "Nettoyage Ouverture").
        schedule_type (ScheduleType): When this routine is expected to run.
        task_templates (list[CleaningTaskTemplate]): All tasks in this routine,
            eagerly loaded for the todo-list view.
    """

    __tablename__ = "cleaning_routines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_type: Mapped[ScheduleType] = mapped_column(
        Enum(ScheduleType, name="cleaning_schedule_type", native_enum=True), nullable=False
    )

    task_templates: Mapped[list[CleaningTaskTemplate]] = relationship(
        "CleaningTaskTemplate",
        back_populates="routine",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CleaningTaskTemplate(TimestampMixin, Base):
    """A reusable task definition within a cleaning routine.

    Defines what must be cleaned (``name`` + optional ``description``) and
    in which zone.  The template is the static definition; ``CleaningLog``
    holds the per-execution record.

    Attributes:
        id (UUID): Primary key.
        routine_id (UUID): FK to the owning routine. CASCADE on delete.
        zone_id (UUID): FK to the associated cleaning zone. RESTRICT on delete
            prevents removing a zone that still has active task templates.
        name (str): Task display name (e.g. "Désinfecter les plans de travail").
        description (str | None): Optional detailed instructions or product
            references for the operator.
        routine (CleaningRoutine): Back-reference to the owning routine.
        zone (CleaningZone): Eagerly loaded zone for the todo-list view.
        logs (list[CleaningLog]): Execution records for this task.
    """

    __tablename__ = "cleaning_task_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cleaning_routines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cleaning_zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    routine: Mapped[CleaningRoutine] = relationship(
        "CleaningRoutine", back_populates="task_templates", lazy="noload"
    )
    zone: Mapped[CleaningZone] = relationship(
        "CleaningZone", back_populates="task_templates", lazy="selectin"
    )
    logs: Mapped[list[CleaningLog]] = relationship(
        "CleaningLog", back_populates="task", cascade="all, delete-orphan", lazy="noload"
    )


class CleaningLog(TimestampMixin, Base):
    """An execution record created when an operator completes a cleaning task.

    One log row is created per task per execution session via the
    ``bulk_create_logs`` service function.  The ``executed_at`` timestamp
    uses the establishment's local time so that HACCP auditors see the
    correct session time even for establishments in non-French timezones.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment (redundant with
            the task→routine→establishment chain, but needed for efficient
            single-table date filtering in ``_build_routine_todo``).
        operator_id (UUID): FK to the operator who executed the task.
            RESTRICT on delete preserves audit integrity.
        task_id (UUID): FK to the task template. RESTRICT on delete.
        status (CleaningStatus): Outcome reported by the operator.
        comment (str | None): Issue description. Mandatory when status is
            ``ISSUE``, optional otherwise.
        executed_at (datetime): Site-local timestamp of task execution.
        task (CleaningTaskTemplate): Back-reference to the task template.
    """

    __tablename__ = "cleaning_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cleaning_task_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[CleaningStatus] = mapped_column(
        Enum(CleaningStatus, name="cleaning_status", native_enum=True), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[CleaningTaskTemplate] = relationship(
        "CleaningTaskTemplate", back_populates="logs", lazy="noload"
    )
