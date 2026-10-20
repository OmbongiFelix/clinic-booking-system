# domains/appointments/router.py
"""HTTP layer only: parse, call the service, shape the response (README §13).

    POST  /appointments                          book            201
    GET   /doctors/{doctor_id}/availability      free slots      200
    PATCH /appointments/{id}/cancel              cancel          200
    PATCH /appointments/{id}/reschedule          reschedule      200
    GET   /patients/{patient_id}/appointments    upcoming        200

Errors are raised as domain exceptions and mapped to the JSON envelope by
core.errors.register_exception_handlers (call it in main.py).
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from clinic_booking_system.core.clock import get_now
from clinic_booking_system.core.config import get_settings
from clinic_booking_system.database.session import get_session

from .schemas import (
    AppointmentCancellationRequest,
    AppointmentRequest,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AvailabilityResponse,
    SlotResponse,
)
from .service import AppointmentService

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_session)) -> AppointmentService:
    return AppointmentService(session)


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    body: AppointmentRequest,
    service: AppointmentService = Depends(get_service),
    now: datetime = Depends(get_now),
) -> AppointmentResponse:
    appt = await service.book(body.patient_id, body.doctor_id, body.start_time, now)
    return AppointmentResponse.from_appointment(appt)


@router.get("/doctors/{doctor_id}/availability", response_model=AvailabilityResponse)
async def get_availability(
    doctor_id: int = Path(gt=0),
    day: date = Query(alias="date", description="YYYY-MM-DD, clinic local date"),
    service: AppointmentService = Depends(get_service),
    now: datetime = Depends(get_now),
) -> AvailabilityResponse:
    slots = await service.availability(doctor_id, day, now)
    return AvailabilityResponse(
        doctor_id=doctor_id,
        date=day,
        timezone=get_settings().CLINIC_TIMEZONE,
        slots=[
            SlotResponse(start_time=s.start_time, end_time=s.end_time) for s in slots
        ],
    )


@router.patch(
    "/appointments/{appointment_id}/cancel", response_model=AppointmentResponse
)
async def cancel_appointment(
    body: AppointmentCancellationRequest,
    appointment_id: int = Path(gt=0),
    service: AppointmentService = Depends(get_service),
    now: datetime = Depends(get_now),
) -> AppointmentResponse:
    appt = await service.cancel(appointment_id, body.reason, now)
    return AppointmentResponse.from_appointment(appt)


@router.patch(
    "/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse
)
async def reschedule_appointment(
    body: AppointmentRescheduleRequest,
    appointment_id: int = Path(gt=0),
    service: AppointmentService = Depends(get_service),
    now: datetime = Depends(get_now),
) -> AppointmentResponse:
    appt = await service.reschedule(
        appointment_id, body.start_time, body.doctor_id, now
    )
    return AppointmentResponse.from_appointment(appt)


@router.get(
    "/patients/{patient_id}/appointments", response_model=list[AppointmentResponse]
)
async def list_patient_appointments(
    patient_id: int = Path(gt=0),
    service: AppointmentService = Depends(get_service),
    now: datetime = Depends(get_now),
) -> list[AppointmentResponse]:
    appts = await service.upcoming_for_patient(patient_id, now)
    return [AppointmentResponse.from_appointment(a) for a in appts]
