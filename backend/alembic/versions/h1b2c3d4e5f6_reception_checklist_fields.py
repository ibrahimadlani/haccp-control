"""reception: add truck checklist and per-item packaging control

Adds one session-level column (truck_condition_ok) and one item-level column
(packaging_ok) to support HACCP delivery reception controls without breaking
existing callers — both columns default to ``true`` so historical rows read
as compliant.

Revision ID: h1b2c3d4e5f6
Revises: a2b3c4d5e6f7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reception_sessions",
        sa.Column("truck_condition_ok", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "reception_items",
        sa.Column("packaging_ok", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("reception_items", "packaging_ok")
    op.drop_column("reception_sessions", "truck_condition_ok")
