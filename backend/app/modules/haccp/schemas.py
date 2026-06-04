"""
Pydantic schemas for the HACCP domain.

Covers two data-capture workflows:

1. **Temperature records** — ``TemperatureRecordCreate`` validates the
   operator-submitted measurement and ``TemperatureRecordResponse`` carries
   the full compliance context (thresholds, conformity flag, linked NC ID)
   needed by the tablet to display the result immediately after submission.

2. **Time clock** — ``PointageCreate`` / ``PointageResponse`` model the
   HR time-clock event log.  ``TimeclockStatus``, ``OperatorTimeclockStatusItem``,
   and ``EstablishmentTimeclockStatusResponse`` support the operator status
   dashboard visible to managers on the supervision portal.

Backward-compatibility aliases ``ReleveTemperatureCreate`` and
``ReleveTemperatureResponse`` are kept to avoid breaking any client code
that still uses the French naming convention.
"""

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.haccp.models import SourceReleve, TypeEvenementPointage

TEMPERATURE_DECIMAL_PATTERN = re.compile(r"^-?\d{1,3}(?:\.\d{1,2})?$")
"""Pre-compiled regex enforcing a maximum of 2 decimal places on temperature values."""


# ── Temperature records ───────────────────────────────────────────────────────


class TemperatureRecordCreate(BaseModel):
    """Request body for submitting a HACCP temperature measurement.

    The ``measured_at`` field defaults to ``None``; when omitted, the service
    uses the current site-local time.  This allows tablets to submit a
    timestamp that was captured earlier (e.g. during a network outage) while
    still anchoring it to the correct establishment timezone.

    Attributes:
        equipment_id (UUID): The equipment being measured.
        measured_value (Decimal): Temperature reading in Celsius (up to 2 d.p.).
        source (SourceReleve): Whether the reading was entered manually or via
            IoT. Defaults to ``MANUEL``.
        measured_at (datetime | None): Timestamp of the measurement. When
            ``None``, the service substitutes ``now_for_site(timezone)``.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "equipment_id": "4a62a65f-1a58-49ec-b4e4-c1d44c02f7ad",
                    "measured_value": "14.00",
                    "source": "MANUEL",
                    "measured_at": "2026-05-25T14:30:00+02:00",
                }
            ]
        }
    )

    equipment_id: UUID
    measured_value: Decimal = Field(max_digits=6, decimal_places=2)
    source: SourceReleve = Field(default=SourceReleve.MANUEL)
    measured_at: datetime | None = Field(default=None)

    @field_validator("measured_value", mode="before")
    @classmethod
    def validate_measured_decimal_format(cls, value: Decimal | str | int | float) -> Decimal:
        """Validate and coerce the measured value to ``Decimal`` with max 2 d.p.

        Args:
            value (Decimal | str | int | float): The raw measurement.

        Returns:
            Decimal: The validated exact decimal representation.

        Raises:
            ValueError: If the value has more than 2 decimal places.
        """
        raw_value = str(value)
        if not TEMPERATURE_DECIMAL_PATTERN.fullmatch(raw_value):
            raise ValueError("Measured value must use up to 2 decimals, e.g. 3.80")
        return Decimal(raw_value)


class TemperatureRecordResponse(BaseModel):
    """Response returned after a temperature record is created.

    Includes the equipment's target thresholds and the computed conformity
    flag so the tablet can display an immediate pass/fail result without an
    additional fetch.

    Attributes:
        id (UUID): Record primary key.
        etablissement_id (UUID): Owning establishment.
        equipment_id (UUID): Measured equipment.
        utilisateur_id (UUID): Operator who recorded the value.
        measured_value (Decimal): The recorded temperature.
        temperature_min_cible (Decimal): Lower threshold from the equipment.
        temperature_max_cible (Decimal): Upper threshold from the equipment.
        is_conforme (bool): ``True`` if the value is within the safe range.
        action_corrective_required (bool): ``True`` when a corrective action
            ticket was automatically opened (i.e. ``not is_conforme``).
        nonconformity_id (UUID | None): The auto-opened NC ticket, if any.
        source (SourceReleve): Whether manual or IoT.
        measured_at (datetime): Timestamp of the measurement (site-local).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    etablissement_id: UUID
    equipment_id: UUID
    utilisateur_id: UUID
    measured_value: Decimal
    temperature_min_cible: Decimal
    temperature_max_cible: Decimal
    is_conforme: bool
    action_corrective_required: bool
    nonconformity_id: UUID | None
    source: SourceReleve
    measured_at: datetime


class ActionCorrectiveResponse(BaseModel):
    """Response body for a corrective action record.

    Attributes:
        id (UUID): Corrective action primary key.
        releve_id (UUID): The source temperature record's primary key.
        utilisateur_id (UUID): The signing operator.
        description (str): Free-text description of the action taken.
        photo_s3_key (str | None): S3 object key of the evidence photo.
        photo_url (str | None): Public URL of the evidence photo, built
            from ``photo_s3_key`` by the S3 service at read time.
        signee_at (datetime): Timestamp of the corrective action signature.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    releve_id: UUID
    utilisateur_id: UUID
    description: str
    photo_s3_key: str | None
    photo_url: str | None
    signee_at: datetime


class EquipmentChoiceResponse(BaseModel):
    """Compact equipment representation for the temperature-record form picker.

    Attributes:
        id (UUID): Equipment primary key.
        name (str): Display name.
        equipment_type (str): Category as a string.
        min_target_temperature (Decimal): Lower threshold.
        max_target_temperature (Decimal): Upper threshold.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    equipment_type: str
    min_target_temperature: Decimal
    max_target_temperature: Decimal


class EquipmentChoiceListResponse(BaseModel):
    """Wrapper response for the equipment picker list.

    Attributes:
        items (list[EquipmentChoiceResponse]): Picker items.
    """

    items: list[EquipmentChoiceResponse]


# Backward-compatibility aliases for French-named clients.
ReleveTemperatureCreate = TemperatureRecordCreate
ReleveTemperatureResponse = TemperatureRecordResponse


# ── Time clock ────────────────────────────────────────────────────────────────


class PointageCreate(BaseModel):
    """Request body for submitting a time-clock event.

    The service validates that ``type_evenement`` represents a permitted
    state-machine transition from the operator's current status before
    writing the record.

    Attributes:
        type_evenement (TypeEvenementPointage): The clock event type
            (CLOCK_IN, BREAK_START, BREAK_END, or CLOCK_OUT).
    """

    type_evenement: TypeEvenementPointage


class PointageResponse(BaseModel):
    """Response body for a created time-clock event.

    Attributes:
        id (UUID): Event primary key.
        etablissement_id (UUID): Owning establishment.
        utilisateur_id (UUID): Operator who submitted the event.
        type_evenement (TypeEvenementPointage): The recorded event type.
        pointe_at (datetime): Site-local timestamp of the event.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    etablissement_id: UUID
    utilisateur_id: UUID
    type_evenement: TypeEvenementPointage
    pointe_at: datetime


class TimeclockStatus(StrEnum):
    """Derived status of an operator's time-clock session.

    Computed from the most recent ``Pointage`` event type.

    Attributes:
        ACTIVE: Operator is clocked in and not on break.
        ON_BREAK: Operator started a break.
        CLOCKED_OUT: Operator is not clocked in.
    """

    ACTIVE = "active"
    ON_BREAK = "on_break"
    CLOCKED_OUT = "clocked_out"


class OperatorTimeclockStatusItem(BaseModel):
    """Current time-clock status for one operator.

    Attributes:
        operator_id (UUID): The operator's primary key.
        operator_name (str | None): Pre-formatted display name, if available.
        status (TimeclockStatus): Derived current status.
        last_event_type (TypeEvenementPointage | None): The most recent event
            type, or ``None`` if the operator has never clocked in.
        last_event_at (datetime | None): Timestamp of the most recent event.
    """

    operator_id: UUID
    operator_name: str | None = None
    status: TimeclockStatus
    last_event_type: TypeEvenementPointage | None
    last_event_at: datetime | None


class EstablishmentTimeclockStatusResponse(BaseModel):
    """Aggregated time-clock status for all operators at an establishment.

    Used by the manager dashboard to display a real-time view of who is
    clocked in, on break, or absent.

    Attributes:
        items (list[OperatorTimeclockStatusItem]): One entry per operator.
    """

    items: list[OperatorTimeclockStatusItem]
