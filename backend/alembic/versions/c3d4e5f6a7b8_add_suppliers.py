"""add suppliers table

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enum types (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE supplier_country AS ENUM (
                'France', 'Belgique', 'Suisse', 'Luxembourg',
                'Allemagne', 'Espagne', 'Italie', 'Pays-Bas',
                'Royaume-Uni', 'Autre'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE supplier_status AS ENUM (
                'pending', 'approved', 'rejected', 'occasional'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    supplier_country = postgresql.ENUM(
        "France",
        "Belgique",
        "Suisse",
        "Luxembourg",
        "Allemagne",
        "Espagne",
        "Italie",
        "Pays-Bas",
        "Royaume-Uni",
        "Autre",
        name="supplier_country",
        create_type=False,
    )
    supplier_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        "occasional",
        name="supplier_status",
        create_type=False,
    )

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_registration_id", sa.String(50), nullable=True),
        sa.Column("country", supplier_country, nullable=False, server_default="France"),
        sa.Column("address", sa.String(1024), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("emergency_contact_name", sa.String(255), nullable=True),
        sa.Column("emergency_phone", sa.String(32), nullable=True),
        sa.Column("status", supplier_status, nullable=False, server_default="pending"),
        sa.Column("approval_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certification_type", sa.String(255), nullable=True),
        sa.Column("internal_notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(op.f("ix_suppliers_establishment_id"), "suppliers", ["establishment_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_suppliers_establishment_id"), table_name="suppliers")
    op.drop_table("suppliers")
    postgresql.ENUM(name="supplier_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="supplier_country").drop(op.get_bind(), checkfirst=True)
