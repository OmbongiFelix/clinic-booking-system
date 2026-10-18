# domains/appointments/repository.py
"""Database access for appointments, via the request's AsyncSession (README §9, §12).

No business rules and no commits here: the service decides what is valid and
owns the transaction. ``add`` flushes so a unique-index violation surfaces
where the service can translate it (README §14.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import STATUS_BOOKED, Appointment


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, appointment_id: int, *, for_update: bool = False) -> Appointment | None:
        """Fetch by id. ``for_update`` takes a row lock (SELECT ... FOR UPDATE) so the
        status check and the change are consistent under concurrency (README §16)."""
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, appointment: Appointment) -> Appointment:
        self._session.add(appointment)
        await self._session.flush()  # may raise IntegrityError (slot taken)
        return appointment

    async def flush(self) -> None:
        await self._session.flush()

    async def booked_starts(
        self, doctor_id: int, start: datetime, end: datetime
    ) -> list[datetime]:
        """Start times of booked appointments for a doctor in [start, end): one range query."""
        stmt = select(Appointment.start_time).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == STATUS_BOOKED,
            Appointment.start_time >= start,
            Appointment.start_time < end,
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def upcoming_for_patient(
        self, patient_id: int, now: datetime
    ) -> Sequence[Appointment]:
        """Booked appointments starting at or after ``now``, earliest first (README §13.5)."""
        stmt = (
            select(Appointment)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status == STATUS_BOOKED,
                Appointment.start_time >= now,
            )
            .order_by(Appointment.start_time.asc())
        )
        return (await self._session.execute(stmt)).scalars().all()