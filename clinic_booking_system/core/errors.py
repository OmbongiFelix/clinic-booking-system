from __future__ import annotations
r"""Domain exceptions and their HTTP mapping"""# core/errors.py
"""Domain exceptions and their HTTP mapping (README §9, §13.6).

Services and pure logic raise these; they never import ``HTTPException``.
``register_exception_handlers`` turns them into the stable JSON envelope:

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""



import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


# ── 404 ──────────────────────────────────────────────────────────────
class DoctorNotFound(AppError):
    status_code, code, default_message = 404, "DOCTOR_NOT_FOUND", "Doctor not found."


class PatientNotFound(AppError):
    status_code, code, default_message = 404, "PATIENT_NOT_FOUND", "Patient not found."


class AppointmentNotFound(AppError):
    status_code, code, default_message = 404, "APPOINTMENT_NOT_FOUND", "Appointment not found."


# ── 409 ──────────────────────────────────────────────────────────────
class SlotUnavailable(AppError):
    status_code, code = 409, "SLOT_UNAVAILABLE"
    default_message = "That slot has already been booked."


class AppointmentAlreadyCancelled(AppError):
    status_code, code = 409, "APPOINTMENT_ALREADY_CANCELLED"
    default_message = "This appointment has already been cancelled."


class AppointmentAlreadyStarted(AppError):
    status_code, code = 409, "APPOINTMENT_ALREADY_STARTED"
    default_message = "This appointment has already started and can no longer be changed."


# ── 422 ──────────────────────────────────────────────────────────────
class SlotMisaligned(AppError):
    status_code, code = 422, "SLOT_MISALIGNED"
    default_message = "Start time must fall on a :00 or :30 boundary (clinic time)."


class SlotOutsideWorkingHours(AppError):
    status_code, code = 422, "SLOT_OUTSIDE_WORKING_HOURS"
    default_message = "The slot is outside the doctor's working hours."


class SlotInPast(AppError):
    status_code, code = 422, "SLOT_IN_PAST"
    default_message = "Start time is in the past."


class SlotTooSoon(AppError):
    status_code, code = 422, "SLOT_TOO_SOON"
    default_message = "Start time is too soon; it must be further ahead."


class SameSlot(AppError):
    status_code, code = 422, "SAME_SLOT"
    default_message = "The appointment is already at that slot."


# ── handlers ─────────────────────────────────────────────────────────
def _envelope(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "message": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return _envelope(422, "REQUEST_VALIDATION", "Invalid request.", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _envelope(500, "INTERNAL_ERROR", "An unexpected error occurred.")