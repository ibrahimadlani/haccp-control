"""add cleaning module (zones, routines, task_templates, logs)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleaning_schedule_type AS ENUM
                ('OPENING', 'CLOSING', 'WEEKLY', 'MONTHLY');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleaning_status AS ENUM ('DONE', 'ISSUE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── cleaning_zones ────────────────────────────────────────────────────────
    op.create_table(
        "cleaning_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # ── cleaning_routines ─────────────────────────────────────────────────────
    op.create_table(
        "cleaning_routines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "schedule_type",
            postgresql.ENUM(
                "OPENING",
                "CLOSING",
                "WEEKLY",
                "MONTHLY",
                name="cleaning_schedule_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # ── cleaning_task_templates ───────────────────────────────────────────────
    op.create_table(
        "cleaning_task_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "routine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cleaning_routines.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cleaning_zones.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # ── cleaning_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "cleaning_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "operator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cleaning_task_templates.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("DONE", "ISSUE", name="cleaning_status", create_type=False),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("cleaning_logs")
    op.drop_table("cleaning_task_templates")
    op.drop_table("cleaning_routines")
    op.drop_table("cleaning_zones")
    op.execute("DROP TYPE IF EXISTS cleaning_status")
    op.execute("DROP TYPE IF EXISTS cleaning_schedule_type")
