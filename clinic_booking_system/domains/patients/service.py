# domains/patients/service.py
"""Public service API for the patients domain (README §9).

``appointments.service`` calls ``get_patient`` here — never the
repository directly. Raises ``PatientNotFound`` so callers don't need
to know the database layer.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from clinic_booking_system.core.errors import PatientNotFound

from .models import Patient
from .repository import PatientRepository


async def get_patient(session: AsyncSession, patient_id: int) -> Patient:
    """Return the patient or raise ``PatientNotFound``.

    Args:
        session: The active database session for this request.
        patient_id: Primary key of the patient to fetch.

    Returns:
        The ``Patient`` ORM object.

    Raises:
        PatientNotFound: If no patient with *patient_id* exists.
    """
    patient = await PatientRepository(session).get(patient_id)
    if patient is None:
        raise PatientNotFound(details={"patient_id": patient_id})
    return patient
