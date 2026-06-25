"""add temperature check constraints

Adds two SQL CHECK constraints that enforce physical plausibility of temperature
data at the database level, independently of application-level validation.

- ``equipements``: ``temperature_min_cible < temperature_max_cible``
  Prevents managers from configuring an inverted threshold range (e.g. min=10°C,
  max=4°C) which would make every reading non-compliant without a clear error.

- ``releves_temperature``: ``valeur_mesuree BETWEEN -50 AND 300``
  Rejects values that are physically impossible for any food-service equipment
  (blast chillers go as low as -40°C; ovens reach 300°C at most).

Revision ID: k4e5f6a7b8c9
Revises: j3d4e5f6a7b8
Create Date: 2026-06-24 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "k4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "j3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "min_lt_max",
        "equipements",
        "temperature_min_cible < temperature_max_cible",
    )
    op.create_check_constraint(
        "valeur_mesuree_range",
        "releves_temperature",
        "valeur_mesuree BETWEEN -50 AND 300",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_releves_temperature_valeur_mesuree_range",
        "releves_temperature",
        type_="check",
    )
    op.drop_constraint(
        "ck_equipements_min_lt_max",
        "equipements",
        type_="check",
    )
