"""add lot traceability schema

Adds the full lot-opening / secondary-DLC schema required by French HACCP
regulations (GBPH restauration) and the CE 178/2002 traceability mandate:

- ``statut_ouverture`` PostgreSQL enum type
- ``products.shelf_life_after_opening_days`` — catalog-level default shelf life
- ``reception_items.is_surgele`` — frozen flag at reception
- ``lot_ouvertures`` table with CHECK constraints (DLC secondaire ≤ DLUO primaire)
- ``production_batches.created_at / updated_at / created_by_id`` — audit trail
- ``production_batch_ingredients`` table with UNIQUE constraint for 1↔N
  batch-to-lot traceability (ascending / descending)

Revision ID: l5f6a7b8c9d0
Revises: k4e5f6a7b8c9
Create Date: 2026-06-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "l5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "k4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- statut_ouverture enum ------------------------------------------------
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE statut_ouverture AS ENUM ('OUVERT', 'CONSOMME', 'JETE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # -- products: shelf life after opening -----------------------------------
    op.add_column(
        "products",
        sa.Column("shelf_life_after_opening_days", sa.Integer(), nullable=True),
    )

    # -- reception_items: frozen flag -----------------------------------------
    op.add_column(
        "reception_items",
        sa.Column(
            "is_surgele",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # -- lot_ouvertures -------------------------------------------------------
    op.create_table(
        "lot_ouvertures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reception_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reception_items.id", ondelete="RESTRICT"),
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
        sa.Column("ouvert_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dluo_primaire", sa.Date(), nullable=False),
        sa.Column("duree_apres_ouverture_jours", sa.Integer(), nullable=False),
        sa.Column("dlc_secondaire_calculee", sa.Date(), nullable=False),
        sa.Column(
            "was_frozen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "statut",
            postgresql.ENUM(
                "OUVERT",
                "CONSOMME",
                "JETE",
                name="statut_ouverture",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'OUVERT'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "dlc_secondaire_calculee <= dluo_primaire",
            name="dlc_secondaire_ne_depasse_pas_primaire",
        ),
        sa.CheckConstraint(
            "duree_apres_ouverture_jours > 0",
            name="duree_apres_ouverture_positive",
        ),
    )

    # -- production_batches: audit trail + operator attribution ---------------
    op.add_column(
        "production_batches",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "production_batches",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "production_batches",
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
    )

    # -- production_batch_ingredients -----------------------------------------
    op.create_table(
        "production_batch_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_batches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reception_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reception_items.id", ondelete="RESTRICT"),
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
        sa.Column("quantity_used", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "batch_id",
            "reception_item_id",
            name="uq_production_batch_ingredients_batch_item",
        ),
    )


def downgrade() -> None:
    op.drop_table("production_batch_ingredients")

    op.drop_column("production_batches", "created_by_id")
    op.drop_column("production_batches", "updated_at")
    op.drop_column("production_batches", "created_at")

    op.drop_table("lot_ouvertures")

    op.drop_column("reception_items", "is_surgele")
    op.drop_column("products", "shelf_life_after_opening_days")

    op.execute("DROP TYPE IF EXISTS statut_ouverture")
