"""
Shared SQLAlchemy declarative base and reusable ORM mixins.

This module is the single source of truth for the ORM base class and the
``TimestampMixin``.  Every domain model throughout ``app/modules/`` inherits
from both ``Base`` and ``TimestampMixin`` to guarantee a consistent table
naming convention and automatic server-side audit timestamps.
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Enforce a consistent constraint-naming convention across all migrations.
# Without this, Alembic would generate anonymous names (e.g. ``None``) for
# foreign-key and unique constraints, making automated downgrade scripts unsafe.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class shared by every SQLAlchemy ORM model in the application.

    All domain models inherit from this class so that they are registered with a
    single ``MetaData`` instance.  Alembic's ``env.py`` imports this base to
    discover all tables for auto-generated migrations.

    Attributes:
        metadata (MetaData): A ``MetaData`` instance configured with the project-wide
            constraint-naming convention.
    """

    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """Mixin that adds server-side ``created_at`` and ``updated_at`` audit columns.

    Both columns are managed by PostgreSQL (``func.now()`` server default and
    ``onupdate`` hook), ensuring accurate timestamps regardless of the client's
    clock or timezone.  No application-level code is required to populate them.

    Attributes:
        created_at (datetime): Timezone-aware timestamp set once at INSERT time.
        updated_at (datetime): Timezone-aware timestamp refreshed on every UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
