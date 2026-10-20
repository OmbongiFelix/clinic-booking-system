# domains/appointments/service.py
# domains/appointments/service.py
"""Appointment business logic (README §7, §13, §14).

Routers call this; this calls the repository and *other domains' services*
(never their repositories). Raises domain errors, never HTTPException.
Owns the transaction: commit on success, rollback on any failure.

Assumed cross-domain interface (README §9), both raising the matching
NotFound error from core.errors:
    doctors.service.get_working_hours(session, doctor_id)
        -> iterable of rows with .weekday (0=Mon), .start_time, .end_time
    patients.service.get_patient(session, patient_id)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from clinic_booking_system.core.config import get_settings
from clinic_booking_system.core.errors import (
    AppointmentAlreadyCancelled,
    AppointmentAlreadyStarted,
    AppointmentNotFound,
    SameSlot,
    SlotUnavailable,
)
from clinic_booking_system.domains.doctors import service as doctors_service
from clinic_booking_system.domains.patients import service as patients_service

from . import scheduling
from .models import STATUS_BOOKED, STATUS_CANCELLED, Appointment
from .repository import AppointmentRepository

_SLOT_INDEX = "uq_appointments_doctor_start_booked"


def _is_slot_conflict(exc: IntegrityError) -> bool:
    return _SLOT_INDEX in str(exc.orig)


class AppointmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AppointmentRepository(session)
        self._settings = get_settings()

    # ── helpers ──────────────────────────────────────────────────────
    async def _validated_utc_start(
        self, doctor_id: int, start_time: datetime, now: datetime
    ) -> datetime:
        hours = await doctors_service.get_working_hours(self._session, doctor_id)  # 404
        scheduling.validate_start_time(
            start_time,
            working_hours=hours,
            now=now,
            lead_minutes=self._settings.MIN_BOOKING_LEAD_MINUTES,
            tz=self._settings.clinic_tz,
        )
        return start_time.astimezone(UTC)

    async def _get_changeable(self, appointment_id: int, now: datetime) -> Appointment:
        """Lock the row and enforce: 404 -> 409 cancelled -> 409 already started."""
        appt = await self._repo.get(appointment_id, for_update=True)
        if appt is None:
            raise AppointmentNotFound(details={"appointment_id": appointment_id})
        if appt.status != STATUS_BOOKED:
            raise AppointmentAlreadyCancelled(
                details={"appointment_id": appointment_id}
            )
        if appt.start_time <= now:
            raise AppointmentAlreadyStarted(details={"appointment_id": appointment_id})
        return appt

    async def _commit(self, appt: Appointment) -> Appointment:
        await self._session.commit()
        await self._session.refresh(appt)  # safe even if expire_on_commit is on
        return appt

    # ── operations ───────────────────────────────────────────────────
    async def book(
        self, patient_id: int, doctor_id: int, start_time: datetime, now: datetime
    ) -> Appointment:
        try:
            start_utc = await self._validated_utc_start(doctor_id, start_time, now)
            await patients_service.get_patient(self._session, patient_id)  # 404
            appt = Appointment(
                doctor_id=doctor_id, patient_id=patient_id, start_time=start_utc
            )
            try:
                await self._repo.add(
                    appt
                )  # flush inside try: unique index decides "taken"
            except IntegrityError as exc:
                if _is_slot_conflict(exc):
                    raise SlotUnavailable(
                        details={
                            "doctor_id": doctor_id,
                            "start_time": start_time.isoformat(),
                        }
                    ) from exc
                raise
            return await self._commit(appt)
        except Exception:
            await self._session.rollback()
            raise

    async def cancel(
        self, appointment_id: int, reason: str, now: datetime
    ) -> Appointment:
        try:
            appt = await self._get_changeable(appointment_id, now)
            appt.status = STATUS_CANCELLED
            appt.cancellation_reason = reason
            appt.cancelled_at = now
            return await self._commit(appt)
        except Exception:
            await self._session.rollback()
            raise

    async def reschedule(
        self,
        appointment_id: int,
        start_time: datetime,
        doctor_id: int | None,
        now: datetime,
    ) -> Appointment:
        try:
            appt = await self._get_changeable(appointment_id, now)
            new_doctor_id = doctor_id or appt.doctor_id
            new_start = await self._validated_utc_start(new_doctor_id, start_time, now)
            if new_doctor_id == appt.doctor_id and new_start == appt.start_time:
                raise SameSlot(details={"appointment_id": appointment_id})

            # Same row, same transaction: old slot freed and new slot taken atomically.
            appt.doctor_id = new_doctor_id
            appt.start_time = new_start
            try:
                await self._repo.flush()
            except IntegrityError as exc:
                if _is_slot_conflict(exc):
                    raise SlotUnavailable(
                        details={
                            "doctor_id": new_doctor_id,
                            "start_time": start_time.isoformat(),
                        }
                    ) from exc
                raise
            return await self._commit(appt)
        except Exception:
            await self._session.rollback()  # original appointment unchanged
            raise

    async def availability(
        self, doctor_id: int, day: date, now: datetime
    ) -> list[scheduling.Slot]:
        hours = list(
            await doctors_service.get_working_hours(self._session, doctor_id)
        )  # 404
        tz = self._settings.clinic_tz
        day_start, day_end = scheduling.day_bounds_utc(day, tz)
        booked = await self._repo.booked_starts(doctor_id, day_start, day_end)
        return scheduling.available_slots(
            day,
            working_hours=hours,
            booked_starts=booked,
            now=now,
            lead_minutes=self._settings.MIN_BOOKING_LEAD_MINUTES,
            tz=tz,
        )

    async def upcoming_for_patient(
        self, patient_id: int, now: datetime
    ) -> Sequence[Appointment]:
        await patients_service.get_patient(self._session, patient_id)  # 404
        return await self._repo.upcoming_for_patient(patient_id, now)
