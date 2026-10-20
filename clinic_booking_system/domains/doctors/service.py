# domains/doctors/service.py
"""Public service API for the doctors domain (README §9).

``appointments.service`` calls ``get_working_hours`` here — never the
repository directly. Raises ``DoctorNotFound`` so callers don't need to
know the database layer.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from clinic_booking_system.core.errors import DoctorNotFound

from .models import Doctor, DoctorWorkingHours
from .repository import DoctorRepository


async def get_doctor(session: AsyncSession, doctor_id: int) -> Doctor:
    """Return the doctor or raise ``DoctorNotFound``.

    Args:
        session: The active database session for this request.
        doctor_id: Primary key of the doctor to fetch.

    Returns:
        The ``Doctor`` ORM object with working hours loaded.

    Raises:
        DoctorNotFound: If no active doctor with *doctor_id* exists.
    """
    doctor = await DoctorRepository(session).get(doctor_id)
    if doctor is None:
        raise DoctorNotFound(details={"doctor_id": doctor_id})
    return doctor


async def get_working_hours(
    session: AsyncSession, doctor_id: int
) -> Sequence[DoctorWorkingHours]:
    """Return the working-hours schedule for *doctor_id* or raise ``DoctorNotFound``.

    A ``DoctorNotFound`` is raised (not an empty list) so that callers can
    distinguish "no doctor" from "doctor exists but has no hours set".

    Args:
        session: The active database session for this request.
        doctor_id: Primary key of the doctor.

    Returns:
        A sequence of ``DoctorWorkingHours`` rows (one per working weekday).

    Raises:
        DoctorNotFound: If no active doctor with *doctor_id* exists.
    """
    # Verify the doctor exists before returning hours.
    await get_doctor(session, doctor_id)
    return await DoctorRepository(session).get_working_hours(doctor_id)
