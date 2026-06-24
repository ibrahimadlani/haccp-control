"""add lot number trigram index

Enables the ``pg_trgm`` extension (if not already present) and adds a GIN
trigram index on ``reception_items.lot_number`` to support fast partial-match
searches for sanitary recall workflows.

Without this index every ``ILIKE '%LG2024%'`` query triggers a full sequential
scan of the ``reception_items`` table.  With the GIN index, PostgreSQL uses the
trigram decomposition to evaluate the predicate with an index-only bitmap scan.

NOTE — zero-downtime production deployments:
  ``CREATE INDEX CONCURRENTLY`` cannot run inside a transaction block and is
  therefore not used here.  For large production tables (millions of rows) run
  the index creation outside of the migration as a separate DBA operation:
      CREATE INDEX CONCURRENTLY ix_reception_items_lot_number_trgm
      ON reception_items USING gin (lot_number gin_trgm_ops);

Revision ID: n7b8c9d0e1f2
Revises: m6a7b8c9d0e1
Create Date: 2026-06-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "m6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.create_index(
        "ix_reception_items_lot_number_trgm",
        "reception_items",
        [sa.text("lot_number gin_trgm_ops")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reception_items_lot_number_trgm",
        table_name="reception_items",
    )
