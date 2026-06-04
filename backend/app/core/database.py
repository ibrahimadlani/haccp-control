"""
Async SQLAlchemy engine and session factory for PostgreSQL.

This module creates a single shared ``AsyncEngine`` and ``AsyncSessionLocal``
factory that are reused for every request.  The ``get_db`` async generator
is the FastAPI dependency injected into all route handlers via
``app.api.deps.DatabaseSession``.

Connection pool settings:
- ``pool_pre_ping=True`` — sends a lightweight ``SELECT 1`` before each
  checkout to detect stale connections after a database restart or
  network interruption, preventing 500 errors on the first request after
  a downtime event.
- ``expire_on_commit=False`` — prevents lazy-load errors when ORM
  instances are accessed after the session is committed but before the
  response is serialised.  This is standard practice for async FastAPI
  apps where the session lifetime ends at commit, not at response end.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    # Detect broken connections before they are handed to a route handler.
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # Instances remain usable after commit — required for FastAPI response serialisation.
    expire_on_commit=False,
    # Explicit flushing keeps control in the service layer; no implicit flushes on query.
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Opens a session from the shared pool, yields it to the request handler,
    and ensures the session is closed (and the connection returned to the pool)
    when the request completes — whether by normal return or by exception.

    Yields:
        AsyncSession: An active async database session scoped to a single HTTP
            request.
    """
    async with AsyncSessionLocal() as session:
        yield session
