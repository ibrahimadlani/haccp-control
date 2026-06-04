"""
ORM models for the Personnel domain.

This module defines the three core identity entities of the application:

- ``Utilisateur`` — a human user who can be assigned to one or more
  establishments in various roles (manager, cook, etc.).
- ``Role`` — a named permission set that controls what a ``Utilisateur``
  can do within an establishment.
- ``AffectationSite`` — the join table that binds a ``Utilisateur`` to an
  ``Etablissement`` with a specific ``Role``.

It also defines the ``Operator`` model, which is the newer, PIN-based identity
used exclusively for tablet-side HACCP signing (temperature records, cleaning
logs, reception checks).  ``Operator`` is intentionally separate from
``Utilisateur`` to allow a clean migration path and to keep the HACCP audit
trail independent of the HR/user management system.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func, text, true
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.tenant.models import Etablissement


class Utilisateur(TimestampMixin, Base):
    """An application user who can be assigned to one or more establishments.

    ``Utilisateur`` is the HR identity model.  A single user can hold different
    roles across multiple establishments (e.g. manager at site A, cook at site B).
    Deletion is always soft (``deleted_at`` timestamp) to preserve audit trails.

    Attributes:
        id (UUID): Primary key.
        nom (str): Last name.
        prenom (str): First name.
        email (str): Unique email address, used as the login identifier.
        telephone_mobile (str | None): Optional mobile phone number.
        mot_de_passe_hash (str): bcrypt hash of the user's password. Never stored
            in plain text.
        code_pin (str | None): bcrypt hash of the 4-digit tablet PIN. ``None``
            until a PIN is explicitly assigned.
        derniere_connexion (datetime | None): UTC timestamp of the last successful
            login, updated by the auth service.
        deleted_at (datetime | None): Soft-delete sentinel. ``None`` means active.
        affectations (list[AffectationSite]): All site assignments for this user.
    """

    __tablename__ = "utilisateurs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    prenom: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    telephone_mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    code_pin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    derniere_connexion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    affectations: Mapped[list[AffectationSite]] = relationship(
        "AffectationSite",
        back_populates="utilisateur",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Role(TimestampMixin, Base):
    """A named permission set used by site assignments.

    Roles are shared across the entire platform (not scoped to a single
    organisation).  The ``permissions`` JSONB column stores a flexible
    key-value map (e.g. ``{"manager": true, "can_manage_device_login": true}``)
    that is evaluated by ``role_utils.is_manager_role`` and similar helpers.

    Attributes:
        id (UUID): Primary key.
        nom_role (str): Unique human-readable role name (e.g. ``"MANAGER"``).
        permissions (dict): JSONB permission flags. Evaluated at runtime by
            ``core.role_utils`` to determine access level.
        affectations (list[AffectationSite]): Back-reference to all assignments
            using this role.
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom_role: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    permissions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    affectations: Mapped[list[AffectationSite]] = relationship(
        "AffectationSite", back_populates="role", lazy="noload"
    )


class AffectationSite(TimestampMixin, Base):
    """Join table that links a Utilisateur to an Etablissement with a specific Role.

    The composite primary key ``(utilisateur_id, etablissement_id, role_id)``
    allows one user to hold multiple roles at the same site simultaneously.
    The ``is_active`` flag is used for soft-deactivation without losing history.

    Attributes:
        utilisateur_id (UUID): FK to ``utilisateurs``.
        etablissement_id (UUID): FK to ``etablissements``.
        role_id (UUID): FK to ``roles``.
        poste_principal (str | None): Optional free-text job title override.
        affecte_le (datetime): Server-side timestamp of when the assignment was created.
        is_active (bool): Whether the assignment is currently active. Deactivation
            preserves the row for audit purposes.
        utilisateur (Utilisateur): Eagerly loaded owning user.
        etablissement (Etablissement): Eagerly loaded owning site.
        role (Role): Eagerly loaded role.
    """

    __tablename__ = "affectations_site"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True
    )
    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("etablissements.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    poste_principal: Mapped[str | None] = mapped_column(String(128), nullable=True)
    affecte_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    utilisateur: Mapped[Utilisateur] = relationship(
        "Utilisateur", back_populates="affectations", lazy="selectin"
    )
    etablissement: Mapped[Etablissement] = relationship(
        "Etablissement", back_populates="affectations", lazy="selectin"
    )
    role: Mapped[Role] = relationship("Role", back_populates="affectations", lazy="selectin")


class OperatorRole(StrEnum):
    """Enumeration of kitchen roles for tablet-signing operators.

    These roles are independent of the HR ``Role`` model and are used solely
    to categorise operators in the HACCP signing context.
    """

    MANAGER = "MANAGER"
    CHEF = "CHEF"
    COMMIS = "COMMIS"
    PLONGEUR = "PLONGEUR"


class Operator(TimestampMixin, Base):
    """A kitchen staff member registered for HACCP action signing on a shared tablet.

    ``Operator`` is the newer, self-contained identity model that replaces the
    legacy ``Utilisateur``+``AffectationSite`` approach for tablet operations.
    It stores its own bcrypt-hashed PIN and compliance dates relevant to French
    food-safety regulations (hygiene training and medical fitness check).

    Key design decisions:
    - ``pin_hash`` is always a bcrypt digest; the raw PIN is never stored.
    - ``is_active = False`` (soft delete) is mandatory to preserve historical
      HACCP signatures — physical row deletion is forbidden.
    - ``hygiene_training_date`` and ``medical_check_date`` expire annually;
      the frontend surfaces warnings when they are ``None`` or older than 12 months.

    Attributes:
        id (UUID): Primary key.
        establishment_id (UUID): FK to the owning establishment. Indexed for
            multi-tenant query performance.
        first_name (str): Operator's given name.
        last_name (str): Operator's family name.
        role (OperatorRole): Kitchen role enum.
        pin_hash (str): bcrypt hash of the 4-digit tablet PIN.
        hygiene_training_date (date | None): Date of last hygiene training. Used
            by the compliance dashboard to flag expired certifications.
        medical_check_date (date | None): Date of last occupational health
            medical check. French food-safety regulation requirement.
        is_active (bool): Soft-delete flag. Always ``True`` for active operators.
    """

    __tablename__ = "operators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    establishment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[OperatorRole] = mapped_column(
        Enum(OperatorRole, name="operator_role", native_enum=True),
        nullable=False,
        default=OperatorRole.COMMIS,
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    hygiene_training_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    medical_check_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
