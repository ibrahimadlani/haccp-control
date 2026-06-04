"""add non_conformities table and migrate actions_correctives

Revision ID: a1b2c3d4e5f6
Revises: 7c19f57a12ab
Create Date: 2026-06-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "7c19f57a12ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 1. Create new PostgreSQL enum types (idempotent via DO block) ---
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE workflow_type AS ENUM ('TEMPERATURE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE nonconformity_status AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # create_type=False tells SQLAlchemy not to issue another CREATE TYPE inside op.create_table
    workflow_type = postgresql.ENUM("TEMPERATURE", name="workflow_type", create_type=False)
    nonconformity_status = postgresql.ENUM(
        "OPEN",
        "IN_PROGRESS",
        "RESOLVED",
        "CLOSED",
        name="nonconformity_status",
        create_type=False,
    )

    # --- 2. Create non_conformities table ---
    op.create_table(
        "non_conformities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "establishment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etablissements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_type", workflow_type, nullable=False),
        sa.Column(
            "status",
            nonconformity_status,
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "source_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("releves_temperature.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "opened_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "assigned_to_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closing_comment", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        op.f("ix_non_conformities_establishment_id"),
        "non_conformities",
        ["establishment_id"],
    )
    op.create_index(
        op.f("ix_non_conformities_opened_by_id"),
        "non_conformities",
        ["opened_by_id"],
    )
    op.create_index(
        op.f("ix_non_conformities_source_record_id"),
        "non_conformities",
        ["source_record_id"],
    )

    # --- 3. Backfill: create one NonConformity per non-compliant temperature record ---
    op.execute("""
        INSERT INTO non_conformities (
            id,
            establishment_id,
            workflow_type,
            status,
            source_record_id,
            opened_by_id,
            opened_at,
            assigned_to_id,
            assigned_at,
            resolved_at,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            r.etablissement_id,
            'TEMPERATURE'::workflow_type,
            (CASE WHEN ac.id IS NOT NULL THEN 'RESOLVED' ELSE 'OPEN' END)::nonconformity_status,
            r.id,
            r.utilisateur_id,
            r.mesure_effectuee_at,
            CASE WHEN ac.id IS NOT NULL THEN ac.utilisateur_id ELSE NULL END,
            CASE WHEN ac.id IS NOT NULL THEN ac.signee_at ELSE NULL END,
            CASE WHEN ac.id IS NOT NULL THEN ac.signee_at ELSE NULL END,
            now(),
            now()
        FROM releves_temperature r
        LEFT JOIN actions_correctives ac ON ac.releve_id = r.id
        WHERE r.is_conforme = false
    """)

    # --- 4. Add nonconformity_id (nullable) to actions_correctives ---
    op.add_column(
        "actions_correctives",
        sa.Column(
            "nonconformity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("non_conformities.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_actions_correctives_nonconformity_id"),
        "actions_correctives",
        ["nonconformity_id"],
    )

    # --- 5. Backfill: link each existing ActionCorrective to its NonConformity ---
    op.execute("""
        UPDATE actions_correctives ac
        SET nonconformity_id = nc.id
        FROM non_conformities nc
        WHERE nc.source_record_id = ac.releve_id
    """)

    # --- 6. Make nonconformity_id NOT NULL and add UNIQUE constraint ---
    op.alter_column("actions_correctives", "nonconformity_id", nullable=False)
    op.create_unique_constraint(
        "uq_actions_correctives_nonconformity_id",
        "actions_correctives",
        ["nonconformity_id"],
    )

    # --- 7. Drop old releve_id FK, unique index and column ---
    op.drop_constraint(
        "fk_actions_correctives_releve_id_releves_temperature",
        "actions_correctives",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_actions_correctives_releve_id",
        table_name="actions_correctives",
    )
    op.drop_column("actions_correctives", "releve_id")


def downgrade() -> None:
    # --- 1. Re-add releve_id column (nullable first) ---
    op.add_column(
        "actions_correctives",
        sa.Column(
            "releve_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("releves_temperature.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # --- 2. Backfill releve_id from non_conformities.source_record_id ---
    op.execute("""
        UPDATE actions_correctives ac
        SET releve_id = nc.source_record_id
        FROM non_conformities nc
        WHERE nc.id = ac.nonconformity_id
    """)

    # --- 3. Make releve_id NOT NULL + UNIQUE ---
    op.alter_column("actions_correctives", "releve_id", nullable=False)
    op.create_unique_constraint(
        "uq_actions_correctives_releve_id",
        "actions_correctives",
        ["releve_id"],
    )
    op.create_index(
        op.f("ix_actions_correctives_releve_id"),
        "actions_correctives",
        ["releve_id"],
    )

    # --- 4. Drop nonconformity_id ---
    op.drop_constraint(
        "uq_actions_correctives_nonconformity_id",
        "actions_correctives",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_actions_correctives_nonconformity_id"),
        table_name="actions_correctives",
    )
    op.drop_column("actions_correctives", "nonconformity_id")

    # --- 5. Drop non_conformities ---
    op.drop_index(op.f("ix_non_conformities_source_record_id"), "non_conformities")
    op.drop_index(op.f("ix_non_conformities_opened_by_id"), "non_conformities")
    op.drop_index(op.f("ix_non_conformities_establishment_id"), "non_conformities")
    op.drop_table("non_conformities")

    # --- 6. Drop enum types ---
    postgresql.ENUM(name="nonconformity_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="workflow_type").drop(op.get_bind(), checkfirst=True)
