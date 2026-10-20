# domains/doctors/repository.py
"""Database access for doctors and working hours (README §9).

No business logic here. The service layer decides what is valid;
these functions just read from the database.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Doctor, DoctorWorkingHours


class DoctorRepository:
    """Read-only access to doctor and working-hours rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, doctor_id: int) -> Doctor | None:
        """Return the doctor with *doctor_id*, or ``None`` if not found.

        Working hours are loaded eagerly in the same query so callers
        don't trigger implicit lazy loads.
        """
        stmt = (
            select(Doctor)
            .where(Doctor.id == doctor_id, Doctor.is_active.is_(True))
            .options(selectinload(Doctor.working_hours))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_working_hours(self, doctor_id: int) -> Sequence[DoctorWorkingHours]:
        """Return all working-hours rows for *doctor_id* (may be empty).

        The caller (``doctors.service``) is responsible for raising
        ``DoctorNotFound`` if the doctor does not exist.
        """
        stmt = select(DoctorWorkingHours).where(
            DoctorWorkingHours.doctor_id == doctor_id
        )
        return (await self._session.execute(stmt)).scalars().all()
