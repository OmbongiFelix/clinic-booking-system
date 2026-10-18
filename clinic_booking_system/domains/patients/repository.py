# domains/patients/repository.py
"""Database access for patient records (README §9).

No business logic here. The service layer is responsible for raising
the correct domain errors.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Patient


class PatientRepository:
    """Read-only access to patient rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, patient_id: int) -> Patient | None:
        """Return the patient with *patient_id*, or ``None`` if not found.

        Args:
            patient_id: Primary key of the patient to look up.

        Returns:
            The ``Patient`` ORM object, or ``None``.
        """
        stmt = select(Patient).where(Patient.id == patient_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()
