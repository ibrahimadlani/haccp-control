"""
Pydantic schemas for the Authentication domain.

This module defines the request/response contracts for the two authentication
flows exposed by the API:

1. **Manager / device login** — a manager logs in with email + password and
   pins a shared kitchen tablet to one establishment.  The response embeds
   safe establishment metadata (no secrets) alongside the JWT.

2. **Organisation supervision login** — an organisation admin logs in to access
   cross-establishment dashboards.  A separate token type is issued to prevent
   scope confusion with device tokens.

Neither flow stores nor returns passwords or raw PINs.
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ManagerLoginRequest(BaseModel):
    """Request body for the manager device-login endpoint.

    Attributes:
        email (EmailStr): Manager's registered email address.
        password (str): Plain-text password (8–72 chars). Verified against the
            bcrypt hash stored in ``Utilisateur.mot_de_passe_hash``.
        etablissement_id (UUID): The establishment the device will be locked to.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    etablissement_id: UUID


class OrganisationLoginRequest(BaseModel):
    """Request body for the organisation supervision login endpoint.

    Attributes:
        email (EmailStr): Organisation admin email.
        password (str): Plain-text password (8–72 chars). Verified against
            ``Organisation.admin_password_hash``.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class EstablishmentTokenMetadata(BaseModel):
    """Safe establishment metadata embedded in the device JWT response.

    Contains only the information a tablet frontend needs to configure itself.
    No secrets, hashes, or internal identifiers beyond the two UUIDs are included.

    Attributes:
        organisation_id (UUID): The owning organisation.
        etablissement_id (UUID): The locked establishment.
        nom_site (str): Human-readable site name for display in the UI header.
        timezone (str): IANA timezone string used to render local timestamps.
        is_org_admin (bool): Whether the logged-in manager is the org admin,
            unlocking cross-establishment management features.
    """

    organisation_id: UUID
    etablissement_id: UUID
    nom_site: str
    timezone: str
    is_org_admin: bool = False


class TokenResponse(BaseModel):
    """Response returned after a successful manager device login.

    Attributes:
        access_token (str): The signed establishment JWT.
        token_type (str): Always ``"bearer"`` per OAuth2 convention.
        establishment (EstablishmentTokenMetadata): Safe site context for the
            frontend to store alongside the token.
    """

    access_token: str
    token_type: str = "bearer"
    establishment: EstablishmentTokenMetadata


class OrganisationTokenMetadata(BaseModel):
    """Safe organisation metadata embedded in the supervision JWT response.

    Attributes:
        organisation_id (UUID): The authenticated organisation's primary key.
        nom_entite (str): Legal entity name displayed in supervision dashboards.
    """

    organisation_id: UUID
    nom_entite: str


class OrganisationTokenResponse(BaseModel):
    """Response returned after a successful organisation supervision login.

    Attributes:
        access_token (str): The signed organisation supervision JWT.
        token_type (str): Always ``"bearer"``.
        organisation (OrganisationTokenMetadata): Safe organisation context.
    """

    access_token: str
    token_type: str = "bearer"
    organisation: OrganisationTokenMetadata


class OperatorListItemResponse(BaseModel):
    """One operator card displayed on the shared-tablet profile selection screen.

    Used by the tablet frontend to render the list of available operators before
    they enter their PIN.  Includes enough information to display a named card
    without exposing any sensitive data.

    Attributes:
        id (UUID): The ``Utilisateur`` primary key, passed as ``X-Operator-Id``
            when the operator submits their PIN.
        nom (str): Last name.
        prenom (str): First name.
        email (EmailStr): Email address.
        nom_complet (str): Pre-formatted full name (``"{prenom} {nom}"``).
        role (str | None): Role name for display; ``None`` when unassigned.
        role_id (UUID | None): Role primary key; ``None`` when unassigned.
        is_active (bool): Whether the operator's assignment is currently active.
    """

    id: UUID
    nom: str
    prenom: str
    email: EmailStr
    nom_complet: str
    role: str | None = None
    role_id: UUID | None = None
    is_active: bool


class EstablishmentPublicResponse(BaseModel):
    """Minimal public establishment metadata returned before authentication.

    Used by the device setup screen to display the site name to the manager
    before they enter their credentials, confirming they have scanned the
    correct QR code or entered the correct establishment ID.

    Attributes:
        etablissement_id (UUID): The establishment's primary key.
        nom_site (str): Site name to display on the setup screen.
        timezone (str): IANA timezone string.
    """

    etablissement_id: UUID
    nom_site: str
    timezone: str
