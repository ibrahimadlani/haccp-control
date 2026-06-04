"""add reception module (products, reception_sessions, reception_items)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extend existing workflow_type enum with RECEPTION value
    op.execute("ALTER TYPE workflow_type ADD VALUE IF NOT EXISTS 'RECEPTION'")

    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column(
            "has_temperature_control",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("min_target_temperature", sa.Float(), nullable=True),
        sa.Column("max_target_temperature", sa.Float(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── reception_status enum ─────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE reception_status AS ENUM ('OPEN', 'CLOSED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── reception_sessions ────────────────────────────────────────────────────
    op.create_table(
        "reception_sessions",
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
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("bl_photo_s3_key", sa.String(1024), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("OPEN", "CLOSED", name="reception_status", create_type=False),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── reception_items ───────────────────────────────────────────────────────
    op.create_table(
        "reception_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reception_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("lot_number", sa.String(128), nullable=False),
        sa.Column("dluo", sa.Date(), nullable=False),
        sa.Column("measured_temperature", sa.Float(), nullable=True),
        sa.Column("is_compliant", sa.Boolean(), nullable=False),
        sa.Column(
            "nc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("non_conformities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("reception_items")
    op.drop_table("reception_sessions")
    op.drop_table("products")
    op.execute("DROP TYPE IF EXISTS reception_status")
    # Note: workflow_type enum value 'RECEPTION' cannot be removed in PostgreSQL
    # without recreating the type. Left in place intentionally.
