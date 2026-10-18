# domains/patients/router.py
"""Patients domain router.

The patient appointments list endpoint
(``GET /patients/{patient_id}/appointments``) is declared in the appointments
router (``domains/appointments/router.py``) because it queries appointments
data and applies the same business rules as other appointment operations.

This router is a placeholder for any future patient-only endpoints
(e.g. ``GET /patients/{id}`` or patient registration).
"""

from fastapi import APIRouter

router = APIRouter(tags=["patients"])
