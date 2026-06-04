"""
ORM models for the Tenant domain (Organisations, Establishments, Subscriptions).

This module defines the top-level multi-tenancy entities:

- ``Organisation`` — the top-level billing and legal entity that owns one or
  more establishments and a single admin account used for the supervision
  dashboard.

- ``Abonnement`` — a Stripe-synchronised billing subscription attached to an
  organisation.  Mirrors Stripe's subscription states to drive feature-gating
  decisions without additional API calls.

- ``Etablissement`` — an operational site (kitchen, restaurant, etc.) that
  belongs to one organisation.  All HACCP data is scoped to an
  ``Etablissement`` via ``establishment_id`` foreign keys throughout the
  application.  Soft deletion via ``deleted_at`` ensures that a decommissioned
  site's audit records remain accessible.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.equipments.models import Equipement
    from app.modules.personnel.models import AffectationSite


class TypeSecteur(StrEnum):
    """Legal sector classification for an organisation.

    Attributes:
        PRIVE: Private-sector entity (restaurant, catering company, etc.).
        PUBLIC: Public-sector entity (school canteen, hospital, etc.).
    """

    PRIVE = "PRIVE"
    PUBLIC = "PUBLIC"


class StatutAbonnement(StrEnum):
    """Stripe subscription lifecycle states mirrored on the Abonnement model.

    These values are kept in sync with Stripe webhook events.  Only
    subscriptions with ``ACTIVE`` or ``TRIALING`` status grant full platform
    access.

    Attributes:
        TRIALING: Free trial period is active.
        ACTIVE: Paid subscription in good standing.
        PAST_DUE: Last invoice payment failed; grace period in effect.
        CANCELED: Subscription explicitly cancelled.
        INCOMPLETE: Initial payment not yet confirmed.
        INCOMPLETE_EXPIRED: Initial payment window expired.
        UNPAID: Multiple payment failures; subscription suspended.
        PAUSED: Subscription temporarily paused.
    """

    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    INCOMPLETE = "INCOMPLETE"
    INCOMPLETE_EXPIRED = "INCOMPLETE_EXPIRED"
    UNPAID = "UNPAID"
    PAUSED = "PAUSED"


class Organisation(TimestampMixin, Base):
    """Top-level tenant entity owning establishments, users, and billing subscriptions.

    A single ``Organisation`` maps to one legal entity (e.g. a restaurant
    group) and owns one admin login for the supervision dashboard.  All other
    users are ``Utilisateur`` records assigned to individual establishments.

    Attributes:
        id (UUID): Primary key.
        nom_entite (str): Legal entity name (e.g. "Groupe Dupont SAS").
        type_secteur (TypeSecteur): Private or public sector classification.
        identifiant_legal (str | None): SIRET or equivalent legal identifier.
        admin_login_email (str | None): Unique email for the organisation admin
            account used on the supervision dashboard.
        admin_password_hash (str | None): bcrypt hash of the admin password.
            ``None`` until an admin account is set up.
        email_facturation (str | None): Billing contact email (may differ from
            ``admin_login_email``).
        adresse_facturation (str | None): Billing address.
        numero_tva_intracommunautaire (str | None): EU VAT number.
        stripe_customer_id (str | None): Stripe customer object ID, used to
            retrieve invoices and manage subscriptions.
        abonnements (list[Abonnement]): All billing subscriptions.
        etablissements (list[Etablissement]): All establishments (lazy-loaded).
    """

    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom_entite: Mapped[str] = mapped_column(String(255), nullable=False)
    type_secteur: Mapped[TypeSecteur] = mapped_column(
        Enum(TypeSecteur, name="type_secteur", native_enum=True), nullable=False
    )
    identifiant_legal: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admin_login_email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)
    admin_password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_facturation: Mapped[str | None] = mapped_column(String(320), nullable=True)
    adresse_facturation: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    numero_tva_intracommunautaire: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    abonnements: Mapped[list[Abonnement]] = relationship(
        "Abonnement", back_populates="organisation", cascade="all, delete-orphan", lazy="selectin"
    )
    etablissements: Mapped[list[Etablissement]] = relationship(
        "Etablissement", back_populates="organisation", lazy="noload"
    )


class Abonnement(TimestampMixin, Base):
    """Billing subscription record synchronised with Stripe.

    One organisation can have multiple ``Abonnement`` rows over time (e.g.
    after plan upgrades or renewals).  The ``stripe_subscription_id`` unique
    constraint ensures idempotent webhook processing.

    Attributes:
        id (UUID): Primary key.
        organisation_id (UUID): FK to the owning organisation.
        stripe_subscription_id (str): Unique Stripe subscription object ID.
        stripe_price_id (str): Stripe price (plan) ID.
        statut (StatutAbonnement): Current Stripe subscription status.
        intervalle (str): Billing interval (e.g. ``"month"``, ``"year"``).
        features_limits (dict): JSONB map of feature limits (e.g. max
            establishments, max operators) derived from the subscribed plan.
        date_debut (datetime): Subscription start date.
        date_fin_periode (datetime | None): Current billing period end date.
        organisation (Organisation): Back-reference to the owning organisation.
    """

    __tablename__ = "abonnements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False)
    statut: Mapped[StatutAbonnement] = mapped_column(
        Enum(StatutAbonnement, name="statut_abonnement", native_enum=True), nullable=False
    )
    intervalle: Mapped[str] = mapped_column(String(32), nullable=False)
    features_limits: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    date_debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_fin_periode: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organisation: Mapped[Organisation] = relationship(
        "Organisation", back_populates="abonnements", lazy="selectin"
    )


class Etablissement(TimestampMixin, Base):
    """An operational site (kitchen, restaurant, etc.) belonging to one organisation.

    Every piece of HACCP data in the application (temperature records,
    cleaning logs, non-conformities, receptions) is scoped to an
    ``Etablissement`` via ``establishment_id`` or ``etablissement_id`` foreign
    keys.  This is the application-level equivalent of Row-Level Security.

    Soft deletion via ``deleted_at`` is mandatory: deleting an establishment
    must not destroy its historical HACCP audit trail.

    Attributes:
        id (UUID): Primary key.
        organisation_id (UUID): FK to the owning organisation.
        nom_site (str): Human-readable site name (e.g. "Restaurant du Parc").
        adresse (str | None): Physical street address.
        siret (str | None): 14-character SIRET number. Unique across all sites.
        type_activite (str | None): Free-text activity type (e.g. "restauration rapide").
        timezone (str): IANA timezone string. Defaults to ``"Europe/Paris"``.
            Used to anchor all HACCP timestamps to local kitchen time.
        telephone_site (str | None): Site telephone number.
        settings (dict): JSONB feature-flag map (e.g. timeclock toggle).
        deleted_at (datetime | None): Soft-delete timestamp. ``None`` = active.
        organisation (Organisation): Back-reference to the owning organisation.
        affectations (list[AffectationSite]): User-to-site assignments.
        equipements (list[Equipement]): Temperature-monitored equipment (lazy-loaded).
    """

    __tablename__ = "etablissements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nom_site: Mapped[str] = mapped_column(String(255), nullable=False)
    adresse: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    siret: Mapped[str | None] = mapped_column(String(14), nullable=True, unique=True)
    type_activite: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/Paris", server_default="Europe/Paris"
    )
    telephone_site: Mapped[str | None] = mapped_column(String(32), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organisation: Mapped[Organisation] = relationship(
        "Organisation", back_populates="etablissements", lazy="selectin"
    )
    # Cross-module relationships use string class names to avoid circular imports
    affectations: Mapped[list[AffectationSite]] = relationship(
        "AffectationSite",
        back_populates="etablissement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    equipements: Mapped[list[Equipement]] = relationship(
        "Equipement", back_populates="etablissement", cascade="all, delete-orphan", lazy="noload"
    )
