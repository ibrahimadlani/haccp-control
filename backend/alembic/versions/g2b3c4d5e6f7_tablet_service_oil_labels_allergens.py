"""tablet service: oil changes, opened labels, daily menu allergens

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "g2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

oil_change_action = postgresql.ENUM("FILTER", "OIL_CHANGE", name="oil_change_action", create_type=False)
storage_location = postgresql.ENUM(
    "COLD_POSITIVE", "COLD_NEGATIVE", "AMBIENT", name="storage_location", create_type=False
)


def upgrade() -> None:
    oil_change_action.create(op.get_bind(), checkfirst=True)
    storage_location.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "oil_change_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("fryer_name", sa.String(length=255), nullable=False),
        sa.Column("action", oil_change_action, nullable=False),
        sa.Column("polar_test_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_conforme", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "opened_product_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secondary_use_by", sa.Date(), nullable=False),
        sa.Column("storage_location", storage_location, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "daily_menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("service_date", sa.Date(), nullable=False, index=True),
        sa.Column("meal_service", sa.String(length=64), nullable=False, server_default="Déjeuner"),
        sa.Column("dish_name", sa.String(length=255), nullable=False),
        sa.Column("allergens", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("daily_menu_items")
    op.drop_table("opened_product_labels")
    op.drop_table("oil_change_records")
    storage_location.drop(op.get_bind(), checkfirst=True)
    oil_change_action.drop(op.get_bind(), checkfirst=True)
