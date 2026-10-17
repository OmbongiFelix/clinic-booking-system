# database/seed.py
"""Idempotent seed script: inserts 5 doctors with Mon–Fri working hours and
3 sample patients so the deployed API can be exercised immediately after
``alembic upgrade head`` (README §19, ambiguity A2).

Run with::

    uv run python -m clinic_booking_system.database.seed

The script uses ``INSERT … ON CONFLICT DO NOTHING`` so it is safe to re-run
against a database that has already been seeded.

Doctor IDs 1–5, Patient IDs 1–3 are the seeded IDs referenced in the
submission details table (README §Submission details).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from clinic_booking_system.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_DOCTORS = [
    {"id": 1, "fullname": "Dr. Amina Osei"},
    {"id": 2, "fullname": "Dr. Brian Mwangi"},
    {"id": 3, "fullname": "Dr. Cecilia Nakato"},
    {"id": 4, "fullname": "Dr. David Karimi"},
    {"id": 5, "fullname": "Dr. Esther Achieng"},
]

# Mon–Fri (weekdays 0–4) 09:00–17:00 clinic time (ambiguity A2).
# Saturday (5) and Sunday (6) are not working days in this seed.
_WORKING_HOURS: list[dict] = []
for _doctor in _DOCTORS:
    for _weekday in range(5):  # 0 = Monday … 4 = Friday
        _WORKING_HOURS.append(
            {
                "doctor_id": _doctor["id"],
                "weekday": _weekday,
                "start_time": time(9, 0),
                "end_time": time(17, 0),
            }
        )

_PATIENTS = [
    {"id": 1, "fullname": "Alice Wanjiru", "email": "alice@example.com", "phone": "+254700000001"},
    {"id": 2, "fullname": "Bob Otieno", "email": "bob@example.com", "phone": "+254700000002"},
    {"id": 3, "fullname": "Carol Muthoni", "email": "carol@example.com", "phone": "+254700000003"},
]


# ---------------------------------------------------------------------------
# Insert helpers (raw SQL so we can use ON CONFLICT DO NOTHING easily)
# ---------------------------------------------------------------------------

async def _seed(session: AsyncSession) -> None:
    """Insert seed rows; skip rows that already exist (idempotent)."""

    # Doctors ----------------------------------------------------------------
    await session.execute(
        text(
            "INSERT INTO doctors (id, fullname, is_active) VALUES (:id, :fullname, true) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        _DOCTORS,
    )

    # Working hours ----------------------------------------------------------
    await session.execute(
        text(
            "INSERT INTO doctor_working_hours (doctor_id, weekday, start_time, end_time) "
            "VALUES (:doctor_id, :weekday, :start_time, :end_time) "
            "ON CONFLICT (doctor_id, weekday) DO NOTHING"
        ),
        _WORKING_HOURS,
    )

    # Patients ---------------------------------------------------------------
    await session.execute(
        text(
            "INSERT INTO patients (id, fullname, email, phone) "
            "VALUES (:id, :fullname, :email, :phone) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        _PATIENTS,
    )

    # Advance the sequences so new inserts don't collide with seed IDs.
    await session.execute(
        text("SELECT setval('doctors_id_seq', (SELECT MAX(id) FROM doctors))")
    )
    await session.execute(
        text("SELECT setval('patients_id_seq', (SELECT MAX(id) FROM patients))")
    )

    await session.commit()
    logger.info("Seed complete: %d doctors, %d patients.", len(_DOCTORS), len(_PATIENTS))


async def main() -> None:
    """Entry point: connect, seed, disconnect."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        await _seed(session)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
