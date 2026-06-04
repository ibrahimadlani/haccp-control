"""
Pydantic schemas for the Tenant domain.

Covers four sub-domains:

1. **Settings** — ``EstablishmentSettings`` and its nested ``TimeclockSettings``
   model represent the JSONB ``settings`` column stored on ``Etablissement``.
   ``from_raw`` safely deserialises the raw dict and applies defaults for
   missing keys.

2. **Organisation** — create and list schemas for organisation tenant records.
   ``OrganisationCreateRequest`` requires a password with a minimum length
   of 12 characters; hashing occurs in the service layer.

3. **Establishment** — create and list schemas for sites, plus equipment and
   user assignment schemas used by the admin panel.  Temperature fields
   on ``SiteEquipmentCreateRequest`` are validated to enforce min < max and
   a maximum of 2 decimal places.

4. **Organisation space** — response schemas for the cross-organisation
   supervision dashboard (overview endpoint).  ``OrganizationOverviewResponse``
   uses field aliases to bridge French ORM attribute names and English API
   contract names.  Backward-compatible French aliases are also exported.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.features import Feature
from app.modules.equipments.models import TypeEquipement
from app.modules.tenant.models import StatutAbonnement, TypeSecteur

# ── Settings ──────────────────────────────────────────────────────────────────


class FeatureToggle(BaseModel):
    """On/off toggle for a single feature on an establishment."""

    enabled: bool = True


class TimeclockSettings(BaseModel):
    """Feature-flag sub-model for the establishment time-clock module.

    Attributes:
        enabled (bool): Whether the timeclock feature is active. Defaults to
            ``True`` on new establishments.
        applies_to_managers (bool): Whether managers must also clock in/out.
            Defaults to ``False``.
    """

    enabled: bool = True
    applies_to_managers: bool = False


class EstablishmentSettings(BaseModel):
    """Structured representation of the ``Etablissement.settings`` JSONB column.

    Each field maps to a Feature enum value. Pydantic applies defaults for
    missing keys so that existing establishments remain unaffected when new
    features are added.
    """

    timeclock: TimeclockSettings = Field(default_factory=TimeclockSettings)
    haccp_temperature: FeatureToggle = Field(default_factory=FeatureToggle)
    cleaning: FeatureToggle = Field(default_factory=FeatureToggle)
    receptions: FeatureToggle = Field(default_factory=FeatureToggle)
    nonconformities: FeatureToggle = Field(default_factory=FeatureToggle)
    suppliers: FeatureToggle = Field(default_factory=FeatureToggle)
    operators: FeatureToggle = Field(default_factory=FeatureToggle)

    @classmethod
    def from_raw(cls, raw: dict) -> "EstablishmentSettings":
        """Deserialise the raw JSONB dict from the database, applying defaults for missing keys."""
        return cls.model_validate(raw) if raw else cls()

    def is_enabled(self, feature: Feature) -> bool:
        """Return True if the feature is active on this establishment."""
        toggle = getattr(self, feature.value, None)
        if toggle is None:
            return True  # unknown feature → permissive by default
        if isinstance(toggle, TimeclockSettings):
            return toggle.enabled
        if isinstance(toggle, FeatureToggle):
            return toggle.enabled
        return True


class EstablishmentSettingsUpdateRequest(BaseModel):
    """Request body for partially updating establishment settings (PATCH semantics).

    Only supplied sub-models are merged into the stored settings; omitted
    sub-models are left unchanged.
    """

    timeclock: TimeclockSettings | None = None
    haccp_temperature: FeatureToggle | None = None
    cleaning: FeatureToggle | None = None
    receptions: FeatureToggle | None = None
    nonconformities: FeatureToggle | None = None
    suppliers: FeatureToggle | None = None
    operators: FeatureToggle | None = None


class PlanLimits(BaseModel):
    """Features and limits granted by the organisation's active subscription.

    Read from ``Abonnement.features_limits`` (JSONB, populated by Stripe webhooks).
    All defaults are generous so that existing accounts without a subscription
    are never accidentally blocked.
    """

    max_establishments: int = Field(default=999)
    max_operators_per_site: int = Field(default=999)
    max_users_per_org: int = Field(default=999)
    features_enabled: list[Feature] = Field(default_factory=lambda: list(Feature))
    plan_name: str = Field(default="unlimited")

    @classmethod
    def from_subscription(cls, features_limits: dict) -> "PlanLimits":
        return cls.model_validate(features_limits) if features_limits else cls()

    def allows(self, feature: Feature) -> bool:
        return feature in self.features_enabled


# ── Organisation ──────────────────────────────────────────────────────────────


class OrganisationCreateRequest(BaseModel):
    """Request body for creating a new organisation tenant.

    The ``admin_password`` field undergoes bcrypt hashing in the service
    layer before storage.  Minimum password length of 12 characters is
    enforced at the schema level.

    Attributes:
        nom_entite (str): Legal entity name (2–255 chars).
        type_secteur (TypeSecteur): Private or public sector.
        identifiant_legal (str | None): SIRET or equivalent (up to 64 chars).
        admin_login_email (EmailStr): Unique email for the organisation admin.
        admin_password (str): Plain-text password (12–72 chars). Hashed in service.
    """

    nom_entite: str = Field(min_length=2, max_length=255)
    type_secteur: TypeSecteur
    identifiant_legal: str | None = Field(default=None, max_length=64)
    admin_login_email: EmailStr
    admin_password: str = Field(min_length=12, max_length=72)


class OrganisationResponse(BaseModel):
    """Response body for organisation list and create endpoints.

    The ``admin_password_hash`` column is deliberately excluded; only the
    email is returned so clients can confirm the admin account without
    exposing credential data.

    Attributes:
        id (UUID): Organisation primary key.
        nom_entite (str): Legal entity name.
        type_secteur (TypeSecteur): Sector classification.
        identifiant_legal (str | None): Legal registration number.
        admin_login_email (EmailStr | None): Admin account email.
    """

    id: UUID
    nom_entite: str
    type_secteur: TypeSecteur
    identifiant_legal: str | None
    admin_login_email: EmailStr | None


class AbonnementListItemResponse(BaseModel):
    """One subscription row in the organisation subscriptions list.

    Attributes:
        id (UUID): Subscription primary key.
        statut (StatutAbonnement): Current Stripe subscription status.
        intervalle (str): Billing interval (``"month"`` or ``"year"``).
        stripe_subscription_id (str): Stripe subscription object ID.
        stripe_price_id (str): Stripe price (plan) object ID.
        date_debut (datetime): Subscription start date.
        date_fin_periode (datetime | None): Current period end date.
    """

    id: UUID
    statut: StatutAbonnement
    intervalle: str
    stripe_subscription_id: str
    stripe_price_id: str
    date_debut: datetime
    date_fin_periode: datetime | None


class AbonnementListResponse(BaseModel):
    """Wrapper response for the organisation subscriptions list endpoint.

    Attributes:
        items (list[AbonnementListItemResponse]): Subscription records ordered
            by ``date_debut`` descending.
    """

    items: list[AbonnementListItemResponse]


# ── Establishment ─────────────────────────────────────────────────────────────


class EstablishmentCreateRequest(BaseModel):
    """Request body for creating a new establishment under an organisation.

    Attributes:
        nom_site (str): Site name (2–255 chars).
        adresse (str | None): Street address (up to 1024 chars).
        siret (str | None): 14-character SIRET number. Must be unique globally.
        type_activite (str | None): Activity type label (up to 128 chars).
        timezone (str): IANA timezone string. Defaults to ``"Europe/Paris"``.
        telephone_site (str | None): Site phone number (up to 32 chars).
    """

    nom_site: str = Field(min_length=2, max_length=255)
    adresse: str | None = Field(default=None, max_length=1024)
    siret: str | None = Field(default=None, min_length=14, max_length=14)
    type_activite: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="Europe/Paris", min_length=2, max_length=64)
    telephone_site: str | None = Field(default=None, max_length=32)


class EstablishmentResponse(BaseModel):
    """Response body for establishment read and create endpoints.

    Attributes:
        id (UUID): Establishment primary key.
        organisation_id (UUID): Owning organisation.
        nom_site (str): Site name.
        adresse (str | None): Street address.
        siret (str | None): SIRET number.
        type_activite (str | None): Activity type.
        timezone (str): IANA timezone string.
        telephone_site (str | None): Site phone number.
        settings (EstablishmentSettings): Feature-flag configuration with
            defaults applied for missing keys.
    """

    id: UUID
    organisation_id: UUID
    nom_site: str
    adresse: str | None
    siret: str | None
    type_activite: str | None
    timezone: str
    telephone_site: str | None
    settings: EstablishmentSettings = Field(default_factory=EstablishmentSettings)


# ── Equipment (admin view) ────────────────────────────────────────────────────


class SiteEquipmentCreateRequest(BaseModel):
    """Request body for adding a piece of equipment to an establishment.

    Temperature fields are validated with a ``Decimal`` type to ensure
    exact decimal representation (no floating-point imprecision) and are
    constrained so that ``min_target_temperature < max_target_temperature``.

    Attributes:
        name (str): Equipment display name (2–255 chars).
        equipment_type (TypeEquipement): Equipment category enum.
        min_target_temperature (Decimal): Lower bound of the safe temperature
            range in Celsius (up to 2 decimal places).
        max_target_temperature (Decimal): Upper bound of the safe temperature
            range in Celsius. Must be strictly greater than ``min_target_temperature``.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Chambre froide positive 1",
                    "equipment_type": "CHAMBRE_FROIDE_POSITIVE",
                    "min_target_temperature": "0.00",
                    "max_target_temperature": "4.00",
                }
            ]
        }
    )

    name: str = Field(min_length=2, max_length=255)
    equipment_type: TypeEquipement
    min_target_temperature: Decimal
    max_target_temperature: Decimal

    @field_validator("min_target_temperature", "max_target_temperature", mode="before")
    @classmethod
    def validate_temperature_decimal_format(cls, value: Decimal | str | int | float) -> Decimal:
        """Coerce temperature input to ``Decimal`` regardless of source type.

        Args:
            value (Decimal | str | int | float): The raw temperature value.

        Returns:
            Decimal: The validated decimal value.
        """
        return Decimal(str(value))

    @model_validator(mode="after")
    def validate_temperature_range(self) -> "SiteEquipmentCreateRequest":
        """Enforce that min temperature is strictly less than max temperature.

        Returns:
            SiteEquipmentCreateRequest: The validated model instance.

        Raises:
            ValueError: If ``min_target_temperature >= max_target_temperature``.
        """
        if self.min_target_temperature >= self.max_target_temperature:
            raise ValueError(
                "min_target_temperature must be strictly lower than max_target_temperature"
            )
        return self


class SiteEquipmentResponse(BaseModel):
    """Response body for one piece of equipment in the admin equipment list.

    Attributes:
        id (UUID): Equipment primary key.
        etablissement_id (UUID): Owning establishment.
        name (str): Equipment display name.
        equipment_type (TypeEquipement): Equipment category.
        min_target_temperature (Decimal): Lower temperature bound.
        max_target_temperature (Decimal): Upper temperature bound.
        is_active (bool): ``False`` if the equipment has been soft-deleted.
    """

    id: UUID
    etablissement_id: UUID
    name: str
    equipment_type: TypeEquipement
    min_target_temperature: Decimal
    max_target_temperature: Decimal
    is_active: bool


class SiteEquipmentListResponse(BaseModel):
    """Wrapper response for the site equipment list endpoint.

    Attributes:
        items (list[SiteEquipmentResponse]): Equipment records sorted by name.
    """

    items: list[SiteEquipmentResponse]


class SiteUserListItemResponse(BaseModel):
    """One user row in the establishment user listing.

    Attributes:
        utilisateur_id (UUID): User primary key.
        nom (str): Last name.
        prenom (str): First name.
        email (EmailStr): Email address.
        role_id (UUID): Primary role assignment primary key.
        role_name (str): Role display name.
        is_active (bool): Whether the assignment is currently active.
    """

    utilisateur_id: UUID
    nom: str
    prenom: str
    email: EmailStr
    role_id: UUID
    role_name: str
    is_active: bool


class SiteUserListResponse(BaseModel):
    """Wrapper response for the establishment user list endpoint.

    Attributes:
        items (list[SiteUserListItemResponse]): User–role–assignment records.
    """

    items: list[SiteUserListItemResponse]


class SiteAffectationCreateRequest(BaseModel):
    """Request body for assigning (or upserting) a user to an establishment.

    If an assignment already exists for the same user/establishment/role
    triple, the service upserts it rather than creating a duplicate row.

    Attributes:
        utilisateur_id (UUID): The user to assign.
        role_id (UUID): The role to grant.
        poste_principal (str | None): Optional free-text job title override.
        is_active (bool): Whether the assignment should be active. Defaults to ``True``.
    """

    utilisateur_id: UUID
    role_id: UUID
    poste_principal: str | None = Field(default=None, max_length=128)
    is_active: bool = True


class SiteAffectationResponse(BaseModel):
    """Response body after creating or updating a site assignment.

    Attributes:
        utilisateur_id (UUID): Assigned user primary key.
        etablissement_id (UUID): Target establishment primary key.
        role_id (UUID): Assigned role primary key.
        poste_principal (str | None): Optional job title override.
        is_active (bool): Current activation state of the assignment.
    """

    utilisateur_id: UUID
    etablissement_id: UUID
    role_id: UUID
    poste_principal: str | None
    is_active: bool


# ── Organisation space (cross-org supervision) ────────────────────────────────


class OrganizationSiteItem(BaseModel):
    """Compact establishment summary used in the organisation overview response.

    Uses a field alias to map the French ORM attribute ``nom_site`` to the
    English API field ``site_name``.

    Attributes:
        id (UUID): Establishment primary key.
        site_name (str): Site display name (alias for ``nom_site``).
        timezone (str): IANA timezone string.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    site_name: str = Field(alias="nom_site")
    timezone: str


class OrganizationUserItem(BaseModel):
    """One user entry in the organisation overview response.

    Uses field aliases to bridge French ORM attribute names and the English
    API contract.

    Attributes:
        id (UUID): User primary key.
        last_name (str): Family name (alias for ``nom``).
        first_name (str): Given name (alias for ``prenom``).
        email (EmailStr): Login email address.
        role (str | None): Primary role name; ``None`` if unassigned.
        site_names (list[str]): Names of all establishments the user is
            assigned to, sorted alphabetically.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    last_name: str = Field(alias="nom")
    first_name: str = Field(alias="prenom")
    email: EmailStr
    role: str | None
    site_names: list[str]


class OrganizationOverviewResponse(BaseModel):
    """Full organisation dashboard payload for the supervision portal.

    Returns all active establishments, managers, and employees in a single
    response to minimise round-trips on the dashboard load.

    Attributes:
        organization_id (UUID): Organisation primary key (alias for ``organisation_id``).
        organization_name (str): Legal entity name (alias for ``nom_entite``).
        establishments (list[OrganizationSiteItem]): Active sites (alias for
            ``etablissements``).
        managers (list[OrganizationUserItem]): Users with a manager-grade role.
        employees (list[OrganizationUserItem]): Users without a manager-grade role
            (alias for ``employes``).
    """

    model_config = ConfigDict(populate_by_name=True)

    organization_id: UUID = Field(alias="organisation_id")
    organization_name: str = Field(alias="nom_entite")
    establishments: list[OrganizationSiteItem] = Field(alias="etablissements")
    managers: list[OrganizationUserItem]
    employees: list[OrganizationUserItem] = Field(alias="employes")
