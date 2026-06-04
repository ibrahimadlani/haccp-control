"""
Pydantic schemas for the Personnel domain.

Covers two distinct sub-domains:

1. **Users** — the admin-facing CRUD interface for ``Utilisateur`` records.
   Passwords are validated for strength at the schema level; hashing happens
   in the service layer.

2. **Operators** — the manager-facing CRUD interface for ``Operator`` records
   used on shared tablets.  All PIN fields are validated with a strict 4-digit
   regex; the raw PIN value is never returned in any response schema.
"""

import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.personnel.models import OperatorRole

# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

TEMPERATURE_DECIMAL_PATTERN = re.compile(r"^-?\d{1,3}(?:\.\d{1,2})?$")
"""Pre-compiled regex for validating temperature decimal format (up to 2 d.p.)."""

_PIN_RE = re.compile(r"^\d{4}$")
"""Pre-compiled regex that enforces the 4-digit numeric PIN contract."""


def validate_password_strength(value: str) -> str:
    """Validate that a password meets the minimum complexity requirements.

    Enforces presence of at least one lowercase letter, one uppercase letter,
    one digit, and one non-alphanumeric symbol.

    Args:
        value (str): The raw password string to validate.

    Returns:
        str: The unchanged password if it passes all checks.

    Raises:
        ValueError: If the password does not meet the complexity requirements.
    """
    has_lower = any(char.islower() for char in value)
    has_upper = any(char.isupper() for char in value)
    has_digit = any(char.isdigit() for char in value)
    has_symbol = any(not char.isalnum() for char in value)
    if not all([has_lower, has_upper, has_digit, has_symbol]):
        raise ValueError(
            "Password must include lowercase, uppercase, digit, and special character."
        )
    return value


# ---------------------------------------------------------------------------
# User schemas (admin CRUD)
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    """Request body for creating a new collaborator and assigning them to establishments.

    The ``password`` field undergoes strength validation at the schema level.
    The ``pin_code`` field is validated as exactly 4 digits.  Both are hashed in
    the service layer; neither is ever stored in plain text.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "last_name": "Dupont",
                    "first_name": "Marie",
                    "email": "marie.dupont@haccp-control.com",
                    "password": "StrongPassw0rd!",
                    "pin_code": "4827",
                    "role_id": "44444444-4444-4444-8444-444444444444",
                    "establishment_ids": ["22222222-2222-4222-8222-222222222222"],
                }
            ]
        }
    )

    last_name: str = Field(min_length=1, max_length=255)
    first_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    pin_code: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    role_id: UUID
    establishment_ids: list[UUID] = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, value: str) -> str:
        """Delegate password complexity check to the shared validator.

        Args:
            value (str): The raw password string.

        Returns:
            str: The unchanged password if valid.

        Raises:
            ValueError: If the password is too weak.
        """
        return validate_password_strength(value)


class UserCreateResponse(BaseModel):
    """Response returned after a successful collaborator creation.

    Attributes:
        user_id (UUID): The newly created ``Utilisateur`` primary key.
        email (EmailStr): The user's email address.
        establishment_ids (list[UUID]): Sites to which the user was assigned.
    """

    user_id: UUID
    email: EmailStr
    establishment_ids: list[UUID]


class UserUpdateRequest(BaseModel):
    """Request body for partially updating a collaborator's profile.

    All fields are optional — only supplied fields are applied (PATCH semantics).
    Supplying ``role_id`` or ``establishment_ids`` triggers a full rebuild of the
    user's ``AffectationSite`` rows for the current organisation.
    """

    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=12, max_length=72)
    pin_code: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    role_id: UUID | None = None
    establishment_ids: list[UUID] | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, value: str | None) -> str | None:
        """Validate the new password if provided.

        Args:
            value (str | None): The raw password string, or ``None`` to skip update.

        Returns:
            str | None: The unchanged password if valid, or ``None``.

        Raises:
            ValueError: If the password is too weak.
        """
        if value is None:
            return value
        return validate_password_strength(value)


class UserSiteSummary(BaseModel):
    """Compact site identifier included in user list responses.

    Attributes:
        establishment_id (UUID): The establishment's primary key.
        site_name (str): Human-readable site name.
    """

    establishment_id: UUID
    site_name: str


class RoleListItemResponse(BaseModel):
    """One role entry for admin forms.

    Attributes:
        id (UUID): The role's primary key.
        role_name (str): The role's unique name (e.g. ``"MANAGER"``).
    """

    id: UUID
    role_name: str


class UserListItemResponse(BaseModel):
    """One collaborator row in the admin user listing.

    Attributes:
        id (UUID): The ``Utilisateur`` primary key.
        last_name (str): Family name.
        first_name (str): Given name.
        email (EmailStr): Login email address.
        role_id (UUID): Primary role assignment.
        role_name (str): Human-readable role name.
        is_active (bool): Whether the user has at least one active assignment.
        sites (list[UserSiteSummary]): All establishments the user is assigned to.
    """

    id: UUID
    last_name: str
    first_name: str
    email: EmailStr
    role_id: UUID
    role_name: str
    is_active: bool
    sites: list[UserSiteSummary]


class UserStatusUpdateRequest(BaseModel):
    """Request body for toggling a collaborator's active status.

    Attributes:
        is_active (bool): The desired activation state.
    """

    is_active: bool


# ---------------------------------------------------------------------------
# Operator schemas (tablet PIN CRUD)
# ---------------------------------------------------------------------------


class OperatorBase(BaseModel):
    """Shared fields for operator create and update operations."""

    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    role: OperatorRole = OperatorRole.COMMIS
    hygiene_training_date: date | None = None
    medical_check_date: date | None = None


class OperatorCreate(OperatorBase):
    """Request body for registering a new tablet operator.

    The ``pin_code`` field is validated as exactly 4 digits and then hashed with
    bcrypt in the service layer.  The raw value is never persisted or returned.
    """

    pin_code: str = Field(description="4-digit PIN — stored hashed, never returned.")

    @model_validator(mode="after")
    def validate_pin(self) -> "OperatorCreate":
        """Enforce the 4-digit numeric PIN contract.

        Returns:
            OperatorCreate: The validated model instance.

        Raises:
            ValueError: If ``pin_code`` does not match ``^\\d{4}$``.
        """
        if not _PIN_RE.match(self.pin_code):
            raise ValueError("Le code PIN doit être composé exactement de 4 chiffres.")
        return self


class OperatorUpdate(BaseModel):
    """Request body for partially updating an operator's profile.

    All fields are optional.  Omitting ``pin_code`` (or leaving it ``None``)
    keeps the existing PIN unchanged — the service layer handles the
    conditional re-hash logic.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: OperatorRole | None = None
    hygiene_training_date: date | None = None
    medical_check_date: date | None = None
    pin_code: str | None = Field(default=None, description="Leave empty to keep current PIN.")

    @model_validator(mode="after")
    def validate_pin_if_provided(self) -> "OperatorUpdate":
        """Validate PIN format only when a new PIN is explicitly supplied.

        Returns:
            OperatorUpdate: The validated model instance.

        Raises:
            ValueError: If a non-``None`` ``pin_code`` does not match ``^\\d{4}$``.
        """
        if self.pin_code is not None and not _PIN_RE.match(self.pin_code):
            raise ValueError("Le code PIN doit être composé exactement de 4 chiffres.")
        return self


class PinResetRequest(BaseModel):
    """Request body for resetting an operator's tablet PIN.

    Attributes:
        pin_code (str): The new 4-digit PIN in plain text; hashed before storage.
    """

    pin_code: str

    @model_validator(mode="after")
    def validate_pin(self) -> "PinResetRequest":
        """Enforce the 4-digit numeric PIN contract on the reset payload.

        Returns:
            PinResetRequest: The validated model instance.

        Raises:
            ValueError: If ``pin_code`` does not match ``^\\d{4}$``.
        """
        if not _PIN_RE.match(self.pin_code):
            raise ValueError("Le code PIN doit être composé exactement de 4 chiffres.")
        return self


class OperatorResponse(BaseModel):
    """Public representation of an operator — PIN hash is never exposed.

    Attributes:
        id (UUID): Operator primary key.
        establishment_id (UUID): Owning establishment.
        first_name (str): Given name.
        last_name (str): Family name.
        role (OperatorRole): Kitchen role.
        hygiene_training_date (date | None): Last hygiene training date.
        medical_check_date (date | None): Last medical check date.
        is_active (bool): Whether the operator is currently active.
    """

    model_config = {"from_attributes": True}

    id: UUID
    establishment_id: UUID
    first_name: str
    last_name: str
    role: OperatorRole
    hygiene_training_date: date | None
    medical_check_date: date | None
    is_active: bool


class OperatorListResponse(BaseModel):
    """Paginated list wrapper for operator list endpoints.

    Attributes:
        items (list[OperatorResponse]): The operator records.
        total (int): Total count of matching operators.
    """

    items: list[OperatorResponse]
    total: int
