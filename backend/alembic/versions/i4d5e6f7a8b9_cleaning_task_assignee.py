"""Add assigned_operator_id to cleaning task templates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "h3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cleaning_task_templates",
        sa.Column(
            "assigned_operator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_cleaning_task_templates_assigned_operator_id",
        "cleaning_task_templates",
        ["assigned_operator_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cleaning_task_templates_assigned_operator_id", "cleaning_task_templates")
    op.drop_column("cleaning_task_templates", "assigned_operator_id")
