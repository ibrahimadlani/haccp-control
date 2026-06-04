"""
Pydantic schemas for the Equipments domain.

Defines request and response schemas for the manager-facing equipment CRUD
endpoints.  Temperature fields use ``Decimal`` for exact precision and are
validated with a regex that enforces a maximum of 2 decimal places
(e.g. ``-18.50`` or ``4.00``).

Two lightweight read-only schemas — ``EquipmentChoiceResponse`` and
``EquipmentChoiceListResponse`` — are used by the HACCP and tablet modules
when building the equipment picker dropdown.
"""

import re
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.equipments.models import TypeEquipement

TEMPERATURE_DECIMAL_PATTERN = re.compile(r"^-?\d{1,3}(?:\.\d{1,2})?$")
"""Pre-compiled regex that accepts temperatures with up to 2 decimal places.

Examples of valid values: ``-22``, ``-18.50``, ``4.00``, ``100.0``.
"""


class EquipmentCreateRequest(BaseModel):
    """Request body for creating a new piece of equipment for a specific establishment.

    Temperature fields are validated for both format (up to 2 d.p.) and range
    (``min < max``) to prevent configuration errors that would make every
    measurement non-compliant.

    Attributes:
        name (str): Equipment display name (2–255 chars).
        equipment_type (TypeEquipement): Equipment category.
        min_target_temperature (Decimal): Lower safe temperature bound (Celsius).
        max_target_temperature (Decimal): Upper safe temperature bound (Celsius).
            Must be strictly greater than ``min_target_temperature``.
        establishment_id (UUID): The establishment to assign this equipment to.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Chambre froide negative zone surgeles",
                    "equipment_type": "CHAMBRE_FROIDE_NEGATIVE",
                    "min_target_temperature": -22.0,
                    "max_target_temperature": -18.0,
                    "establishment_id": "22222222-2222-4222-8222-222222222222",
                }
            ]
        }
    )

    name: str = Field(min_length=2, max_length=255)
    equipment_type: TypeEquipement
    min_target_temperature: Decimal
    max_target_temperature: Decimal
    establishment_id: UUID

    @field_validator("min_target_temperature", "max_target_temperature", mode="before")
    @classmethod
    def validate_temperature_decimal_format(cls, value: Decimal | str | int | float) -> Decimal:
        """Validate and coerce temperature input to ``Decimal`` with max 2 d.p.

        Args:
            value (Decimal | str | int | float): The raw temperature value.

        Returns:
            Decimal: The validated exact decimal representation.

        Raises:
            ValueError: If the value has more than 2 decimal places or
                does not match the expected numeric format.
        """
        raw_value = str(value)
        if not TEMPERATURE_DECIMAL_PATTERN.fullmatch(raw_value):
            raise ValueError("Temperature must use up to 2 decimals, e.g. -18.50 or 4.00")
        return Decimal(raw_value)

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "EquipmentCreateRequest":
        """Enforce that min temperature is strictly less than max temperature.

        Returns:
            EquipmentCreateRequest: The validated model instance.

        Raises:
            ValueError: If ``min_target_temperature >= max_target_temperature``.
        """
        if self.min_target_temperature >= self.max_target_temperature:
            raise ValueError(
                "min_target_temperature must be strictly lower than max_target_temperature"
            )
        return self


class EquipmentUpdateRequest(BaseModel):
    """Request body for partially updating a piece of equipment (PATCH semantics).

    All fields are optional.  When both temperature fields are supplied,
    the range constraint (``min < max``) is re-validated.

    Attributes:
        name (str | None): New display name (2–255 chars).
        equipment_type (TypeEquipement | None): New equipment category.
        min_target_temperature (Decimal | None): New lower temperature bound.
        max_target_temperature (Decimal | None): New upper temperature bound.
    """

    name: str | None = Field(default=None, min_length=2, max_length=255)
    equipment_type: TypeEquipement | None = None
    min_target_temperature: Decimal | None = None
    max_target_temperature: Decimal | None = None

    @field_validator("min_target_temperature", "max_target_temperature", mode="before")
    @classmethod
    def validate_temperature_decimal_format(
        cls, value: Decimal | str | int | float | None
    ) -> Decimal | None:
        """Validate decimal format for temperature fields when provided.

        Args:
            value (Decimal | str | int | float | None): The raw value, or
                ``None`` to leave the existing threshold unchanged.

        Returns:
            Decimal | None: The validated decimal or ``None``.

        Raises:
            ValueError: If the value does not match the expected format.
        """
        if value is None:
            return None
        raw_value = str(value)
        if not TEMPERATURE_DECIMAL_PATTERN.fullmatch(raw_value):
            raise ValueError("Temperature must use up to 2 decimals, e.g. -18.50 or 4.00")
        return Decimal(raw_value)

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "EquipmentUpdateRequest":
        """Re-validate the temperature range when both fields are present.

        Returns:
            EquipmentUpdateRequest: The validated model instance.

        Raises:
            ValueError: If both temperatures are supplied and ``min >= max``.
        """
        if (
            self.min_target_temperature is not None
            and self.max_target_temperature is not None
            and self.min_target_temperature >= self.max_target_temperature
        ):
            raise ValueError(
                "min_target_temperature must be strictly lower than max_target_temperature"
            )
        return self


class EquipmentResponse(BaseModel):
    """Full equipment representation returned by read and write endpoints.

    Attributes:
        id (UUID): Equipment primary key.
        name (str): Display name.
        equipment_type (TypeEquipement): Equipment category.
        min_target_temperature (Decimal): Lower safe temperature bound.
        max_target_temperature (Decimal): Upper safe temperature bound.
        establishment_id (UUID): Owning establishment.
        establishment_site_name (str): Human-readable site name (denormalised
            for the frontend — avoids an extra request to fetch the site name).
        is_active (bool): ``False`` if the equipment has been soft-deleted.
    """

    id: UUID
    name: str
    equipment_type: TypeEquipement
    min_target_temperature: Decimal
    max_target_temperature: Decimal
    establishment_id: UUID
    establishment_site_name: str
    is_active: bool


class EquipmentListResponse(BaseModel):
    """Wrapper response for the equipment list endpoint.

    Attributes:
        items (list[EquipmentResponse]): Equipment records sorted by name.
    """

    items: list[EquipmentResponse]


class EquipmentChoiceResponse(BaseModel):
    """Compact equipment representation for dropdown pickers on the tablet.

    Used by the HACCP temperature-record form to populate the equipment
    selector.  Excludes ``establishment_site_name`` and ``is_active`` to
    keep the payload minimal.

    Attributes:
        id (UUID): Equipment primary key.
        name (str): Display name.
        equipment_type (str): Equipment category as a string.
        min_target_temperature (Decimal): Lower temperature bound.
        max_target_temperature (Decimal): Upper temperature bound.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    equipment_type: str
    min_target_temperature: Decimal
    max_target_temperature: Decimal


class EquipmentChoiceListResponse(BaseModel):
    """Wrapper response for the equipment choice list.

    Attributes:
        items (list[EquipmentChoiceResponse]): Equipment picker items.
    """

    items: list[EquipmentChoiceResponse]
