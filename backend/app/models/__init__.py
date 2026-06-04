"""
Alembic compatibility shim — re-exports Base and all ORM models.

This module exists for two reasons:

1. **Alembic autogenerate** — ``alembic/env.py`` imports ``Base`` from this
   package.  All domain models must be imported here (even if unused) so that
   SQLAlchemy's mapper registry is fully populated before Alembic inspects
   ``Base.metadata`` for schema differences.

2. **Legacy imports** — any code or test that was written before the modular
   refactoring and still does ``from app.models import SomeModel`` continues to
   work without modification.

Do NOT add business logic here.  This file must remain a pure import aggregator.
"""

from app.core.base import Base, TimestampMixin  # noqa: F401
from app.modules.catalog.models import (  # noqa: F401
    Product,
    Supplier,
    SupplierCountry,
    SupplierStatus,
)

# ---------------------------------------------------------------------------
# Import all domain models to register them with the SQLAlchemy mapper.
# Order does not matter for registration, but it is kept alphabetical for
# readability.  The ``noqa: F401`` suppresses "imported but unused" warnings
# since the side-effect (mapper registration) is the whole point.
# ---------------------------------------------------------------------------
from app.modules.cleaning.models import (  # noqa: F401
    CleaningLog,
    CleaningRoutine,
    CleaningStatus,
    CleaningTaskTemplate,
    CleaningZone,
    ScheduleType,
)
from app.modules.equipments.models import Equipement, TypeEquipement  # noqa: F401
from app.modules.haccp.models import (  # noqa: F401
    Pointage,
    ReleveTemperature,
    SourceReleve,
    TypeEvenementPointage,
)
from app.modules.nonconformities.models import (  # noqa: F401
    ActionCorrective,
    NonConformity,
    NonConformityStatus,
    WorkflowType,
)
from app.modules.personnel.models import (  # noqa: F401
    AffectationSite,
    Operator,
    OperatorRole,
    Role,
    Utilisateur,
)
from app.modules.receptions.models import (  # noqa: F401
    ReceptionItem,
    ReceptionSession,
    ReceptionStatus,
)
from app.modules.tenant.models import (  # noqa: F401
    Abonnement,
    Etablissement,
    Organisation,
    StatutAbonnement,
    TypeSecteur,
)

__all__ = [
    "Abonnement",
    "ActionCorrective",
    "AffectationSite",
    "Base",
    "CleaningLog",
    "CleaningRoutine",
    "CleaningStatus",
    "CleaningTaskTemplate",
    "CleaningZone",
    "Equipement",
    "Etablissement",
    "NonConformity",
    "NonConformityStatus",
    "Operator",
    "OperatorRole",
    "Organisation",
    "Pointage",
    "Product",
    "ReceptionItem",
    "ReceptionSession",
    "ReceptionStatus",
    "ReleveTemperature",
    "Role",
    "ScheduleType",
    "SourceReleve",
    "StatutAbonnement",
    "Supplier",
    "SupplierCountry",
    "SupplierStatus",
    "TimestampMixin",
    "TypeEvenementPointage",
    "TypeEquipement",
    "TypeSecteur",
    "Utilisateur",
    "WorkflowType",
]
