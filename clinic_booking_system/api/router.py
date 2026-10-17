# api/router.py
"""Top-level API router: mounts domain routers and the /health endpoint.

No business logic lives here — this file is composition only. Each domain
router is mounted at root (``/``) so the paths declared in the domain files
(e.g. ``/appointments``, ``/doctors/{id}/availability``) are the final paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clinic_booking_system.database.session import get_session
from clinic_booking_system.domains.appointments.router import router as appointments_router

router = APIRouter()

# ── Domain routers ──────────────────────────────────────────────────────────
# All endpoints (appointments, availability, cancel, reschedule, patient list)
# are declared in the appointments router (README §8).
router.include_router(appointments_router)


# ── Health endpoint ─────────────────────────────────────────────────────────
@router.get("/health", tags=["ops"])
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    """Liveness and database reachability check (README §13, NFR5).

    Runs ``SELECT 1`` against the database. The deployment smoke test in
    ``cd.yml`` polls this endpoint after every deploy.

    Args:
        session: Injected database session (FastAPI dependency).

    Returns:
        ``{"status": "ok", "database": "ok"}`` when everything is healthy.
        A 500 response with a standard error envelope when the database
        is unreachable (the generic exception handler in ``core/errors.py``
        handles the unexpected exception and logs it server-side).
    """
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}