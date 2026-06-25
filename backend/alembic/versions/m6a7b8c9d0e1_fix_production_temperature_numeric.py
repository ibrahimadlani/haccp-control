"""fix production temperature to numeric

Converts ``production_steps.temperature_mesuree`` from ``DOUBLE PRECISION``
(Float) to ``NUMERIC(6, 2)`` to eliminate IEEE 754 rounding errors that can
cause a legitimate 74.0°C reading to be stored as 73.9999…, silently
triggering a false non-conformity alert for poultry (volaille) batches.

Also adds the CHECK constraint that enforces physical plausibility of all
temperature measurements recorded for production steps.

Revision ID: m6a7b8c9d0e1
Revises: l5f6a7b8c9d0
Create Date: 2026-06-24 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "m6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "l5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE production_steps
        ALTER COLUMN temperature_mesuree
        TYPE NUMERIC(6, 2)
        USING temperature_mesuree::NUMERIC(6, 2)
    """)

    op.create_check_constraint(
        "production_step_temperature_range",
        "production_steps",
        "temperature_mesuree BETWEEN -50 AND 300",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_production_steps_production_step_temperature_range",
        "production_steps",
        type_="check",
    )

    op.execute("""
        ALTER TABLE production_steps
        ALTER COLUMN temperature_mesuree
        TYPE DOUBLE PRECISION
        USING temperature_mesuree::DOUBLE PRECISION
    """)
