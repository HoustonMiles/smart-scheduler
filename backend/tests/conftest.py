"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
from datetime import date, datetime
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database_models import Base, User
from app.database import get_session


# Configure asyncio for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create basic test client"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def db_session():
    """
    Create a test database session with in-memory SQLite
    This creates a fresh database for each test
    """
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        app.dependency_overrides[get_session] = lambda: session
        yield session
        app.dependency_overrides.clear()
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
def test_user():
    """Create a test user object (not persisted)"""
    return User(
        id=1,
        email="test@example.com",
        google_id="test_google_id",
        name="Test User",
        is_active=True
    )


@pytest.fixture
def test_user_2():
    """Create a second test user for multi-user tests"""
    return User(
        id=2,
        email="test2@example.com",
        google_id="test_google_id_2",
        name="Test User 2",
        is_active=True
    )


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        "title": "Test Task",
        "total_duration": 120,
        "min_session": 30,
        "max_session": 60,
        "due_date": (date.today()).isoformat(),
        "priority": 1,
        "allow_overlap": False,
        "once_per_day": False
    }

@pytest.fixture(autouse=True)
def setup_logging():
    """Initialize logging for tests"""
    from app.core.logging_config import setup_logging
    setup_logging(environment="test")
    yield
