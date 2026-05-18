import os
from contextlib import asynccontextmanager

# Override DATABASE_URL BEFORE any app imports so the global engine targets test DB
_test_db_url = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://app:devpassword@localhost:5432/safety_response_test",
)
os.environ["DATABASE_URL"] = _test_db_url

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.modules.auth.router import create_access_token, hash_password
from app.modules.events.models import Event
from app.modules.notifications.models import Reminder
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

# Replace lifespan with no-op so seed_data never runs during tests
@asynccontextmanager
async def _noop_lifespan(application):
    yield

app.router.lifespan_context = _noop_lifespan

TEST_DATABASE_URL = _test_db_url


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database():
    """Create tables once per session. Engine is disposed immediately so no asyncpg
    connection persists into the per-test (function-scoped) event loop."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(setup_database):
    """Per-test engine+connection ensures asyncpg runs in the same function-scoped
    event loop as the test itself, preventing cross-loop Future errors."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    connection = await engine.connect()
    trans = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def admin_user(db_session) -> User:
    user = User(
        employee_id="TEST_A001",
        name="Test Admin",
        email="test.admin@example.com",
        password_hash=hash_password("testpassword"),
        role="admin",
        department="IT",
        facility="TestFab",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture()
async def manager_user(db_session) -> User:
    user = User(
        employee_id="TEST_M001",
        name="Test Manager",
        email="test.manager@example.com",
        password_hash=hash_password("testpassword"),
        role="manager",
        department="Engineering",
        facility="TestFab",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture()
async def employee_user(db_session, manager_user) -> User:
    user = User(
        employee_id="TEST_E001",
        name="Test Employee",
        email="test.employee@example.com",
        password_hash=hash_password("testpassword"),
        role="employee",
        department="Engineering",
        facility="TestFab",
        manager_id=manager_user.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------------------
# Auth header fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_headers(admin_user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(admin_user.id))}"}


@pytest.fixture()
def manager_headers(manager_user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(manager_user.id))}"}


@pytest.fixture()
def employee_headers(employee_user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(employee_user.id))}"}


# ---------------------------------------------------------------------------
# Event fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def active_event(db_session, admin_user, manager_user, employee_user) -> Event:
    event = Event(
        title="Test Earthquake Event",
        description="A test event",
        event_type="earthquake",
        severity="high",
        status="active",
        facility=["TestFab"],
        created_by=admin_user.id,
    )
    db_session.add(event)
    await db_session.flush()

    # Manually create placeholder reports (mimicking create_event business logic)
    for user in [admin_user, manager_user, employee_user]:
        report = SafetyReport(event_id=event.id, user_id=user.id)
        db_session.add(report)
    await db_session.flush()
    return event
