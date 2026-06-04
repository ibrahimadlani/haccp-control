"""
FastAPI dependency type aliases for the API layer.

This module centralises the ``Annotated`` dependency types consumed by every
router in ``app/modules/``.  Using named aliases instead of repeating the full
``Annotated[..., Depends(...)]`` expression at every endpoint keeps route
signatures concise and ensures a single place to swap the underlying dependency
function if the authentication strategy changes.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    CurrentEstablishment,
    CurrentOrganisation,
    get_current_establishment,
    get_current_operator,
    get_current_organisation,
)
from app.core.feature_flags import require_feature  # noqa: F401  re-exported for router imports
from app.modules.personnel.models import Utilisateur

# Injected async database session — resolved from the connection pool via get_db.
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]

# Authenticated establishment context — decoded from the shared-device JWT.
# Guarantees multi-tenant Row-Level Security: all queries must filter by
# ``CurrentEstablishment.etablissement_id``.
CurrentSite = Annotated[CurrentEstablishment, Depends(get_current_establishment)]

# Authenticated organisation context — decoded from the organisation supervision JWT.
CurrentOrg = Annotated[CurrentOrganisation, Depends(get_current_organisation)]

# The operator (``Utilisateur``) who signed in via PIN on the shared tablet.
# Used by endpoints that require an active operator identity (e.g. temperature
# records, cleaning logs).
CurrentOperator = Annotated[Utilisateur, Depends(get_current_operator)]
