"""expand type_equipement enum

Revision ID: 6f8ea9a2b8a7
Revises: 4d2b6cf6dca1
Create Date: 2026-05-25 19:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "6f8ea9a2b8a7"
down_revision: str | Sequence[str] | None = "4d2b6cf6dca1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'REFRIGERATEUR_VIANDE'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'REFRIGERATEUR_POISSON'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'VITRINE_CHAUFFANTE'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'CELLULE_REFROIDISSEMENT'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'CHAUFFE_ASSIETTE_FOUR'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'CONGELATEUR_CONSERVATEUR'")
    op.execute("ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS 'RESERVE_SECHE'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely without type recreation.
    pass
