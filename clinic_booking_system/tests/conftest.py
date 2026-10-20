# tests/conftest.py
"""Shared pytest fixtures for the Clinic Booking System test suite.

Structure:
- Unit tests (tests/unit/): no database; fast; test pure scheduling logic.
- Integration tests (tests/integration/): run against a real PostgreSQL
  database (the CI PostgreSQL service container or local ``docker compose``).

The ``DATABASE_URL`` environment variable must point to a test database.
The test database is distinct from the production database so integration
tests can create and destroy data freely.

Async tests use ``pytest-asyncio`` with ``asyncio_mode = "auto"`` (set in
``pyproject.toml``), so ``async def test_…`` functions run automatically.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import clinic_booking_system.database.models_registry  # noqa: F401 — register all models
from clinic_booking_system.core.clock import get_now
from clinic_booking_system.core.config import get_settings
from clinic_booking_system.database.db import Base
from clinic_booking_system.database.session import get_session
from clinic_booking_system.main import app

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test async engine and all tables; drop them after the session."""
    settings = get_settings()
    test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def session(engine):
    """Yield a fresh AsyncSession for each test, rolling back afterwards.

    Using a nested transaction (SAVEPOINT) means each test sees an empty
    database without the cost of dropping and recreating tables.
    """
    connection = await engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
    async with session_factory() as s:
        yield s
        await s.rollback()  # Ensures clean state for the next test

    await transaction.rollback()
    await connection.close()


# ---------------------------------------------------------------------------
# Seeded-data fixtures (used by integration tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def seeded_db(session):
    """Seed minimal doctor, working-hours and patient rows for integration tests.

    Returns a dict with ``doctor_id`` and ``patient_id`` for use in tests.
    """

    from sqlalchemy import text

    # Insert a doctor
    row = await session.execute(
        text(
            "INSERT INTO doctors (fullname, is_active) VALUES ('Dr. Test', true) "
            "RETURNING id"
        )
    )
    doctor_id = row.scalar_one()

    # Mon–Fri 09:00–17:00
    for weekday in range(5):
        await session.execute(
            text(
                "INSERT INTO doctor_working_hours (doctor_id, weekday, start_time, end_time) "
                "VALUES (:did, :wd, '09:00', '17:00')"
            ),
            {"did": doctor_id, "wd": weekday},
        )

    # Insert a patient
    row = await session.execute(
        text(
            "INSERT INTO patients (fullname, email, phone) "
            "VALUES ('Test Patient', 'test@example.com', '+1234567890') "
            "RETURNING id"
        )
    )
    patient_id = row.scalar_one()

    await session.flush()
    return {"doctor_id": doctor_id, "patient_id": patient_id}


@pytest_asyncio.fixture()
async def committed_seed(engine):
    from sqlalchemy import text

    async with engine.begin() as conn:  # commits on exit
        doctor_id = (
            await conn.execute(
                text(
                    "INSERT INTO doctors (fullname, is_active) VALUES ('Dr. Race', true) RETURNING id"
                )
            )
        ).scalar_one()
        for wd in range(5):
            await conn.execute(
                text(
                    "INSERT INTO doctor_working_hours (doctor_id, weekday, start_time, end_time) "
                    "VALUES (:d, :w, '09:00', '17:00')"
                ),
                {"d": doctor_id, "w": wd},
            )
        patient_id = (
            await conn.execute(
                text(
                    "INSERT INTO patients (fullname, email, phone) "
                    "VALUES ('Race Patient', 'race@example.com', '+1234567891') RETURNING id"
                )
            )
        ).scalar_one()
    yield {"doctor_id": doctor_id, "patient_id": patient_id}
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM appointments WHERE doctor_id = :d"), {"d": doctor_id}
        )
        await conn.execute(
            text("DELETE FROM doctor_working_hours WHERE doctor_id = :d"),
            {"d": doctor_id},
        )
        await conn.execute(text("DELETE FROM doctors WHERE id = :d"), {"d": doctor_id})
        await conn.execute(
            text("DELETE FROM patients WHERE id = :p"), {"p": patient_id}
        )


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(session):
    """Return an httpx AsyncClient wired to the FastAPI app.

    Overrides ``get_session`` so every request uses the test's rolled-back
    session, and overrides ``get_now`` so time-dependent rules are stable.
    """
    # Use a fixed "now" well in the past relative to test slot times so
    # tests that check booking rules always have enough lead time.
    fixed_now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    async def _override_session():
        yield session

    def _override_now():
        return fixed_now

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_now] = _override_now

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()
