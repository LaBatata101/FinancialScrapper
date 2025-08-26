from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db import AsyncDbSessionManager, get_async_db


@pytest.fixture
def mock_engine():
    """Mock async engine for testing"""
    engine = AsyncMock(spec=AsyncEngine)
    return engine


@pytest.fixture
def mock_sessionmaker():
    """Mock session maker for testing"""
    sessionmaker = MagicMock()
    return sessionmaker


class TestAsyncDbSessionManager:
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test that AsyncDbSessionManager initializes correctly"""
        with (
            patch("app.db.create_async_engine") as mock_create_engine,
            patch("app.db.async_sessionmaker") as mock_sessionmaker,
        ):

            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            _manager = AsyncDbSessionManager("postgresql://test", {"echo": True})

            mock_create_engine.assert_called_once_with("postgresql://test", echo=True)
            mock_sessionmaker.assert_called_once_with(
                autocommit=False, autoflush=False, bind=mock_engine, expire_on_commit=False
            )

    @pytest.mark.asyncio
    async def test_close_success(self):
        """Test successful close of database manager"""
        with patch("app.db.create_async_engine") as mock_create_engine, patch("app.db.async_sessionmaker"):

            mock_engine = AsyncMock()
            mock_create_engine.return_value = mock_engine

            manager = AsyncDbSessionManager("postgresql://test")
            await manager.close()

            mock_engine.dispose.assert_called_once()
            assert manager._engine is None
            assert manager._sessionmaker is None

    @pytest.mark.asyncio
    async def test_close_not_initialized(self):
        """Test close when manager is not initialized"""
        manager = AsyncDbSessionManager.__new__(AsyncDbSessionManager)
        manager._engine = None

        with pytest.raises(Exception, match="DatabaseSessionManager is not initialized"):
            await manager.close()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful database connection"""
        with patch("app.db.create_async_engine") as mock_create_engine, patch("app.db.async_sessionmaker"):

            mock_engine = AsyncMock()
            mock_connection = AsyncMock()

            async_context_manager = AsyncMock()
            async_context_manager.__aenter__ = AsyncMock(return_value=mock_connection)
            async_context_manager.__aexit__ = AsyncMock(return_value=None)

            mock_engine.begin = MagicMock(return_value=async_context_manager)

            mock_create_engine.return_value = mock_engine

            manager = AsyncDbSessionManager("postgresql://test")

            async with manager.connect() as conn:
                assert conn == mock_connection

    @pytest.mark.asyncio
    async def test_connect_with_exception(self):
        """Test database connection with exception and rollback"""
        with patch("app.db.create_async_engine") as mock_create_engine, patch("app.db.async_sessionmaker"):

            mock_engine = AsyncMock()
            mock_connection = AsyncMock()

            async_context_manager = AsyncMock()
            async_context_manager.__aenter__ = AsyncMock(return_value=mock_connection)
            async_context_manager.__aexit__ = AsyncMock(return_value=None)

            mock_engine.begin = MagicMock(return_value=async_context_manager)

            mock_create_engine.return_value = mock_engine

            manager = AsyncDbSessionManager("postgresql://test")

            with pytest.raises(SQLAlchemyError):
                async with manager.connect() as conn:
                    raise SQLAlchemyError("Database error")

            mock_connection.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_not_initialized(self):
        """Test connect when engine is not initialized"""
        manager = AsyncDbSessionManager.__new__(AsyncDbSessionManager)
        manager._engine = None

        with pytest.raises(Exception, match="DatabaseSessionManager is not initialized"):
            async with manager.connect():
                pass

    @pytest.mark.asyncio
    async def test_session_success(self):
        """Test successful database session"""
        with patch("app.db.create_async_engine"), patch("app.db.async_sessionmaker") as mock_sessionmaker:

            mock_session = AsyncMock(spec=AsyncSession)
            mock_sessionmaker_instance = MagicMock()
            mock_sessionmaker_instance.return_value = mock_session
            mock_sessionmaker.return_value = mock_sessionmaker_instance

            manager = AsyncDbSessionManager("postgresql://test")

            async with manager.session() as session:
                assert session == mock_session

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_with_exception(self):
        """Test database session with exception and rollback"""
        with patch("app.db.create_async_engine"), patch("app.db.async_sessionmaker") as mock_sessionmaker:

            mock_session = AsyncMock(spec=AsyncSession)
            mock_sessionmaker_instance = MagicMock()
            mock_sessionmaker_instance.return_value = mock_session
            mock_sessionmaker.return_value = mock_sessionmaker_instance

            manager = AsyncDbSessionManager("postgresql://test")

            with pytest.raises(SQLAlchemyError):
                async with manager.session() as session:
                    raise SQLAlchemyError("Session error")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_not_initialized(self):
        """Test session when sessionmaker is not initialized"""
        manager = AsyncDbSessionManager.__new__(AsyncDbSessionManager)
        manager._sessionmaker = None

        with pytest.raises(Exception, match="DatabaseSessionManager is not initialized"):
            async with manager.session():
                pass


class TestGetAsyncDb:
    @pytest.mark.asyncio
    async def test_get_async_db(self):
        """Test the get_async_db dependency injection function"""
        with patch("app.db.AsyncSessionLocal") as mock_session_local:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_local.session.return_value.__aenter__.return_value = mock_session

            async for db in get_async_db():
                assert db == mock_session
                break
