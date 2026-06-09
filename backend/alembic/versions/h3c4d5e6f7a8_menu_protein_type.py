"""Add protein_type to daily_menu_items for cooking temperature thresholds."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "g2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

protein_type = postgresql.ENUM(
    "POULTRY",
    "MINCED_MEAT",
    "WHOLE_MEAT",
    "FISH",
    "VEGETARIAN",
    "OTHER",
    name="menu_protein_type",
    create_type=False,
)


def upgrade() -> None:
    protein_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "daily_menu_items",
        sa.Column(
            "protein_type",
            protein_type,
            nullable=False,
            server_default="WHOLE_MEAT",
        ),
    )


def downgrade() -> None:
    op.drop_column("daily_menu_items", "protein_type")
    protein_type.drop(op.get_bind(), checkfirst=True)
