import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from app.db import get_async_db
from app.db.models import Base
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    """Creates an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Creates database tables before testing and deletes them afterward."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provides a database session for testing."""
    async with TestingSessionLocal() as session:
        await session.begin_nested()

        yield session

        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def api_client(db_session: AsyncSession) -> AsyncClient:
    """Provides an asynchronous HTTP client for testing the API."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_async_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
