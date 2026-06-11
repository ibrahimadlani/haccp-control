"""production: food_type and HACCP step types

Revision ID: j3d4e5f6a7b8
Revises: i2c3d4e5f6a7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "j3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "i2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE production_food_type AS ENUM (
                'VOLAILLE', 'VIANDE_HACHEE', 'VIANDE_PIECE',
                'LEGUMES_FECULENTS', 'POISSON', 'AUTRE'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.add_column(
        "production_batches",
        sa.Column(
            "food_type",
            postgresql.ENUM(
                "VOLAILLE",
                "VIANDE_HACHEE",
                "VIANDE_PIECE",
                "LEGUMES_FECULENTS",
                "POISSON",
                "AUTRE",
                name="production_food_type",
                create_type=False,
            ),
            nullable=False,
            server_default="AUTRE",
        ),
    )

    op.execute("ALTER TYPE production_step_type RENAME TO production_step_type_old")
    op.execute("""
        CREATE TYPE production_step_type AS ENUM (
            'CUISSON_A_COEUR', 'REFROIDISSEMENT_DEBUT', 'REFROIDISSEMENT_FIN'
        )
    """)
    op.execute("""
        ALTER TABLE production_steps
        ALTER COLUMN step_type TYPE production_step_type
        USING (
            CASE step_type::text
                WHEN 'CUISSON' THEN 'CUISSON_A_COEUR'
                WHEN 'REFROIDISSEMENT' THEN 'REFROIDISSEMENT_FIN'
                ELSE step_type::text
            END
        )::production_step_type
    """)
    op.execute("DROP TYPE production_step_type_old")


def downgrade() -> None:
    op.execute("ALTER TYPE production_step_type RENAME TO production_step_type_old")
    op.execute("""
        CREATE TYPE production_step_type AS ENUM ('CUISSON', 'REFROIDISSEMENT')
    """)
    op.execute("""
        ALTER TABLE production_steps
        ALTER COLUMN step_type TYPE production_step_type
        USING (
            CASE step_type::text
                WHEN 'CUISSON_A_COEUR' THEN 'CUISSON'
                WHEN 'REFROIDISSEMENT_DEBUT' THEN 'REFROIDISSEMENT'
                WHEN 'REFROIDISSEMENT_FIN' THEN 'REFROIDISSEMENT'
                ELSE 'CUISSON'
            END
        )::production_step_type
    """)
    op.execute("DROP TYPE production_step_type_old")
    op.drop_column("production_batches", "food_type")
    op.execute("DROP TYPE IF EXISTS production_food_type")
