"""tablet canteen: reception checklist, production temps, witness samples

Revision ID: f1a2b3c4d5e6
Revises: h1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "h1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

production_control_type = postgresql.ENUM(
    "COOKING_CORE",
    "HOT_HOLDING",
    name="production_control_type",
    create_type=False,
)


def upgrade() -> None:
    # truck_condition_ok déjà ajouté par h1b2c3d4e5f6
    op.add_column(
        "reception_sessions",
        sa.Column("packaging_integrity_ok", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "reception_sessions",
        sa.Column(
            "canned_goods_inspected_ok", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "reception_sessions",
        sa.Column("lab_report_s3_key", sa.String(length=1024), nullable=True),
    )

    production_control_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "production_temperature_records",
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
        sa.Column("dish_name", sa.String(length=255), nullable=False),
        sa.Column("control_type", production_control_type, nullable=False),
        sa.Column("measured_value", sa.Numeric(6, 2), nullable=False),
        sa.Column("min_required_c", sa.Numeric(6, 2), nullable=False, server_default="63"),
        sa.Column("is_conforme", sa.Boolean(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
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
        "witness_samples",
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
        sa.Column("dish_name", sa.String(length=255), nullable=False),
        sa.Column("meal_service", sa.String(length=64), nullable=False, server_default="Déjeuner"),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discard_on", sa.Date(), nullable=False),
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
    op.drop_table("witness_samples")
    op.drop_table("production_temperature_records")
    op.drop_column("reception_sessions", "lab_report_s3_key")
    op.drop_column("reception_sessions", "canned_goods_inspected_ok")
    op.drop_column("reception_sessions", "packaging_integrity_ok")
    production_control_type.drop(op.get_bind(), checkfirst=True)
