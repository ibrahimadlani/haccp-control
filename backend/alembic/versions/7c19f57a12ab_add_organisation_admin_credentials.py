"""add organisation admin credentials

Revision ID: 7c19f57a12ab
Revises: 6f8ea9a2b8a7
Create Date: 2026-05-25 20:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c19f57a12ab"
down_revision: str | Sequence[str] | None = "6f8ea9a2b8a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organisations", sa.Column("admin_login_email", sa.String(length=320), nullable=True)
    )
    op.add_column(
        "organisations", sa.Column("admin_password_hash", sa.String(length=255), nullable=True)
    )
    op.create_unique_constraint(
        "uq_organisations_admin_login_email", "organisations", ["admin_login_email"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_organisations_admin_login_email", "organisations", type_="unique")
    op.drop_column("organisations", "admin_password_hash")
    op.drop_column("organisations", "admin_login_email")
