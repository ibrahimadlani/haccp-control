"""add type_equipement to equipements

Revision ID: 4d2b6cf6dca1
Revises: bf5974834806
Create Date: 2026-05-25 18:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4d2b6cf6dca1"
down_revision: str | Sequence[str] | None = "bf5974834806"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    type_equipement = postgresql.ENUM(
        "CHAMBRE_FROIDE_POSITIVE",
        "CHAMBRE_FROIDE_NEGATIVE",
        "VITRINE_REFRIGEREE",
        "AUTRE",
        name="type_equipement",
    )
    type_equipement.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "equipements",
        sa.Column(
            "type_equipement",
            type_equipement,
            nullable=False,
            server_default="AUTRE",
        ),
    )


def downgrade() -> None:
    op.drop_column("equipements", "type_equipement")

    type_equipement = postgresql.ENUM(
        "CHAMBRE_FROIDE_POSITIVE",
        "CHAMBRE_FROIDE_NEGATIVE",
        "VITRINE_REFRIGEREE",
        "AUTRE",
        name="type_equipement",
    )
    type_equipement.drop(op.get_bind(), checkfirst=True)
