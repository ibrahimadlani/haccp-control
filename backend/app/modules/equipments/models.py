"""
ORM models for the Equipments domain.

Defines the ``Equipement`` model — a physical piece of temperature-controlled
equipment (cold room, refrigerator, display case, etc.) installed at an
establishment.  Each ``Equipement`` record carries the HACCP-mandated safe
temperature range (``temperature_min_cible`` / ``temperature_max_cible``)
against which every temperature reading is validated at write time.

``TypeEquipement`` enumerates the equipment categories recognised by French
food-safety inspectors and drives the display icon and default temperature
thresholds in the tablet UI.

Soft deletion (``deleted_at``) is used instead of physical row removal to
preserve the foreign-key reference from historical ``ReleveTemperature`` rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.haccp.models import ReleveTemperature
    from app.modules.tenant.models import Etablissement


class TypeEquipement(StrEnum):
    """Equipment category used for display grouping and icon selection in the UI.

    Temperature thresholds differ by category (e.g. positive cold rooms target
    0–4 °C while negative ones target −22 to −18 °C).  The tablet uses this
    enum to pre-fill default thresholds when a manager adds new equipment.

    Attributes:
        CHAMBRE_FROIDE_POSITIVE: Positive cold room (0–4 °C range).
        CHAMBRE_FROIDE_NEGATIVE: Negative cold room / freezer (−22 to −18 °C).
        REFRIGERATEUR_VIANDE: Meat refrigerator.
        REFRIGERATEUR_POISSON: Fish refrigerator.
        VITRINE_REFRIGEREE: Refrigerated display case.
        VITRINE_CHAUFFANTE: Heated display case.
        CELLULE_REFROIDISSEMENT: Blast chiller.
        CHAUFFE_ASSIETTE_FOUR: Plate warmer or oven.
        CONGELATEUR_CONSERVATEUR: Chest freezer.
        RESERVE_SECHE: Dry goods storage (ambient temperature monitoring).
        AUTRE: Any other equipment type not covered by the above categories.
    """

    CHAMBRE_FROIDE_POSITIVE = "CHAMBRE_FROIDE_POSITIVE"
    CHAMBRE_FROIDE_NEGATIVE = "CHAMBRE_FROIDE_NEGATIVE"
    REFRIGERATEUR_VIANDE = "REFRIGERATEUR_VIANDE"
    REFRIGERATEUR_POISSON = "REFRIGERATEUR_POISSON"
    VITRINE_REFRIGEREE = "VITRINE_REFRIGEREE"
    VITRINE_CHAUFFANTE = "VITRINE_CHAUFFANTE"
    CELLULE_REFROIDISSEMENT = "CELLULE_REFROIDISSEMENT"
    CHAUFFE_ASSIETTE_FOUR = "CHAUFFE_ASSIETTE_FOUR"
    CONGELATEUR_CONSERVATEUR = "CONGELATEUR_CONSERVATEUR"
    RESERVE_SECHE = "RESERVE_SECHE"
    AUTRE = "AUTRE"


class Equipement(TimestampMixin, Base):
    """A temperature-controlled piece of equipment monitored by HACCP records.

    Each ``Equipement`` defines the safe temperature envelope for its category.
    When an operator records a temperature measurement, the service compares
    ``valeur_mesuree`` against ``temperature_min_cible`` / ``temperature_max_cible``
    and automatically opens a ``NonConformity`` ticket if the value falls outside.

    Soft deletion via ``deleted_at`` ensures that historical
    ``ReleveTemperature`` rows retain their FK reference even after the
    equipment is retired from active monitoring.

    Attributes:
        id (UUID): Primary key.
        etablissement_id (UUID): FK to the owning establishment. Indexed for
            multi-tenant query performance.
        nom (str): Display name (e.g. "Chambre froide positive 1").
        type_equipement (TypeEquipement): Equipment category enum.
        temperature_min_cible (Decimal): Lower bound of the safe temperature
            range in Celsius. Stored with 6-digit precision, 2 decimal places.
        temperature_max_cible (Decimal): Upper bound of the safe temperature
            range. Must be strictly greater than ``temperature_min_cible``.
        deleted_at (datetime | None): Soft-delete timestamp. ``None`` = active.
        etablissement (Etablissement): Eagerly loaded owning establishment.
        releves (list[ReleveTemperature]): Temperature readings (lazy-loaded).
    """

    __tablename__ = "equipements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    etablissement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etablissements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type_equipement: Mapped[TypeEquipement] = mapped_column(
        Enum(TypeEquipement, name="type_equipement", native_enum=True),
        nullable=False,
        default=TypeEquipement.AUTRE,
        server_default=TypeEquipement.AUTRE.value,
    )
    temperature_min_cible: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    temperature_max_cible: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    etablissement: Mapped[Etablissement] = relationship(
        "Etablissement", back_populates="equipements", lazy="selectin"
    )
    releves: Mapped[list[ReleveTemperature]] = relationship(
        "ReleveTemperature",
        back_populates="equipement",
        cascade="all, delete-orphan",
        lazy="noload",
    )
