"""replace delivery_date with received_at on reception_sessions

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("reception_sessions", "delivery_date")
    op.add_column(
        "reception_sessions",
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("reception_sessions", "received_at")
    op.add_column(
        "reception_sessions",
        sa.Column(
            "delivery_date",
            sa.Date(),
            nullable=False,
            server_default=sa.func.current_date(),
        ),
    )
