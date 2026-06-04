"""catalogue produits : gtin, is_active, renommage colonnes, supplier NOT NULL

Revision ID: a2b3c4d5e6f7
Revises: d0e1f2a3b4c5
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Rename columns to match canonical naming ───────────────────────────────
    op.alter_column("products", "reference", new_column_name="internal_reference")
    op.alter_column("products", "min_target_temperature", new_column_name="min_temperature")
    op.alter_column("products", "max_target_temperature", new_column_name="max_temperature")

    # ── Add new columns ────────────────────────────────────────────────────────
    op.add_column("products", sa.Column("gtin", sa.String(128), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # ── Index for barcode lookups ──────────────────────────────────────────────
    op.create_index("ix_products_gtin", "products", ["gtin"])

    # ── supplier_id: SET NULL → RESTRICT + NOT NULL ────────────────────────────
    # Verified: 0 existing rows have supplier_id IS NULL.
    op.drop_constraint("fk_products_supplier_id_suppliers", "products", type_="foreignkey")
    op.alter_column(
        "products",
        "supplier_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_products_supplier_id_suppliers",
        "products",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_supplier_id_suppliers", "products", type_="foreignkey")
    op.alter_column(
        "products",
        "supplier_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_products_supplier_id_suppliers",
        "products",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index("ix_products_gtin", table_name="products")
    op.drop_column("products", "is_active")
    op.drop_column("products", "gtin")

    op.alter_column("products", "min_temperature", new_column_name="min_target_temperature")
    op.alter_column("products", "max_temperature", new_column_name="max_target_temperature")
    op.alter_column("products", "internal_reference", new_column_name="reference")
