"""add production module (batches, steps)

Revision ID: i2c3d4e5f6a7
Revises: h1b2c3d4e5f6
Create Date: 2026-06-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "i2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "h1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE production_batch_statut AS ENUM ('EN_COURS', 'TERMINE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE production_step_type AS ENUM ('CUISSON', 'REFROIDISSEMENT');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "production_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "etablissement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("nom_recette", sa.String(255), nullable=False),
        sa.Column("date_production", sa.Date(), nullable=False),
        sa.Column(
            "statut",
            postgresql.ENUM(
                "EN_COURS",
                "TERMINE",
                name="production_batch_statut",
                create_type=False,
            ),
            nullable=False,
            server_default="EN_COURS",
        ),
    )

    op.create_table(
        "production_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_batches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "step_type",
            postgresql.ENUM(
                "CUISSON",
                "REFROIDISSEMENT",
                name="production_step_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("temperature_mesuree", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "operator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("production_steps")
    op.drop_table("production_batches")
    op.execute("DROP TYPE IF EXISTS production_step_type")
    op.execute("DROP TYPE IF EXISTS production_batch_statut")
