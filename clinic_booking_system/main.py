# main.py
"""FastAPI application entrypoint for the Clinic Booking System (README §7).

This is the only file that should be passed to ``uvicorn``
(``uvicorn clinic_booking_system.main:app``). All request-handling logic
lives in ``api/`` and ``domains/`` — this file is **composition only**:

- Creates the ``FastAPI`` app instance.
- Imports ``database.models_registry`` so all ORM models are registered
  with the shared ``Base.metadata`` before Alembic or any query runs.
- Registers domain exception handlers from ``core.errors``.
- Mounts the top-level API router from ``api.router``.
"""

# Ensure all ORM model classes are imported and registered with Base.metadata
# before anything else (Alembic env.py and the session pool rely on this).
import clinic_booking_system.database.models_registry  # noqa: F401

from fastapi import FastAPI

from clinic_booking_system.api.router import router
from clinic_booking_system.core.errors import register_exception_handlers

app = FastAPI(
    title="Clinic Booking System",
    version="1.0.0",
    description=(
        "REST API for booking, cancelling and rescheduling appointments "
        "at a small clinic with 5 doctors and 30-minute slots."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Wire up domain-exception → JSON-envelope handlers (README §13.6).
register_exception_handlers(app)

# Mount all routes (appointments, availability, health, etc.).
app.include_router(router)