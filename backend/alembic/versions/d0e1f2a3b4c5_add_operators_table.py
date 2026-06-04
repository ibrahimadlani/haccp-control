"""add operators table with role enum and compliance dates

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE operator_role AS ENUM
                ('MANAGER', 'CHEF', 'COMMIS', 'PLONGEUR');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "operators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "MANAGER",
                "CHEF",
                "COMMIS",
                "PLONGEUR",
                name="operator_role",
                create_type=False,
            ),
            nullable=False,
            server_default="COMMIS",
        ),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("hygiene_training_date", sa.Date(), nullable=True),
        sa.Column("medical_check_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("operators")
    op.execute("DROP TYPE IF EXISTS operator_role")
