# domains/doctors/router.py
"""Doctors domain router.

The availability endpoint (``GET /doctors/{doctor_id}/availability``) is
declared in the appointments router (``domains/appointments/router.py``)
because it requires both working-hours data (doctors domain) and booked-slots
data (appointments domain) — see README §7.

This router is a placeholder for any future doctor-only endpoints
(e.g. ``GET /doctors`` or ``GET /doctors/{id}``).
"""

from fastapi import APIRouter

router = APIRouter(tags=["doctors"])
