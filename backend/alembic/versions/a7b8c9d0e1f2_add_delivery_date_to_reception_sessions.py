"""add delivery_date to reception_sessions

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reception_sessions",
        sa.Column(
            "delivery_date",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
    )


def downgrade() -> None:
    op.drop_column("reception_sessions", "delivery_date")
