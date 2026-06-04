import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import get_db
from app.core.s3 import get_s3_service
from app.main import app
from app.models import Base


@pytest.fixture(scope="function")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide one event loop for async SQLAlchemy and httpx fixtures."""

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _test_database_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://haccp_user:haccp_password@db:5432/haccp_control_test",
    )


async def _ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database
    if database_name is None:
        raise RuntimeError("TEST_DATABASE_URL must include a database name.")

    connection = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database_name,
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    database_url = _test_database_url()
    await _ensure_database_exists(database_url)

    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield one async DB session per test and drop all test tables afterwards."""

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    table_names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    if table_names:
        async with test_engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@dataclass
class MockS3Service:
    uploaded_key: str = "tests/mock-upload.png"

    async def upload_image(self, *_args, **_kwargs) -> str:
        return self.uploaded_key

    def object_url(self, key: str) -> str:
        return f"http://test-s3.local/{key}"


@pytest.fixture(scope="function")
def mock_s3() -> MockS3Service:
    return MockS3Service()


@pytest_asyncio.fixture(scope="function")
async def client(
    test_db: AsyncSession,
    mock_s3: MockS3Service,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    def override_get_s3_service() -> MockS3Service:
        return mock_s3

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_s3_service] = override_get_s3_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()
