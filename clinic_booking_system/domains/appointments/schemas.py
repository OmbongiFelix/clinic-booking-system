# domains/appointments/schemas.py
"""Pydantic request/response contracts for the public API (README §13)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from clinic_booking_system.core.config import get_settings

from .models import Appointment
from .scheduling import slot_end

# Trimmed, 1-500 characters (README §13.3).
CancelReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class AppointmentRequest(BaseModel):
    """Body for POST /appointments. Naive datetimes are rejected (A13)."""

    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    start_time: AwareDatetime


class AppointmentCancellationRequest(BaseModel):
    """Body for PATCH /appointments/{id}/cancel. The id is in the path."""

    reason: CancelReason


class AppointmentRescheduleRequest(BaseModel):
    """Body for PATCH /appointments/{id}/reschedule. ``doctor_id`` defaults to the current doctor (A9)."""

    start_time: AwareDatetime = Field(
        description="New start time, ISO 8601 with offset"
    )
    doctor_id: int | None = Field(default=None, gt=0)


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime

    @classmethod
    def from_appointment(cls, appt: Appointment) -> AppointmentResponse:
        tz = get_settings().clinic_tz
        return cls(
            id=appt.id,
            patient_id=appt.patient_id,
            doctor_id=appt.doctor_id,
            start_time=appt.start_time.astimezone(tz),
            end_time=slot_end(appt.start_time).astimezone(tz),
            status=appt.status,
            cancellation_reason=appt.cancellation_reason,
            cancelled_at=appt.cancelled_at.astimezone(tz)
            if appt.cancelled_at
            else None,
            created_at=appt.created_at.astimezone(tz),
        )


class SlotResponse(BaseModel):
    start_time: datetime
    end_time: datetime


class AvailabilityResponse(BaseModel):
    doctor_id: int
    date: date
    timezone: str
    slots: list[SlotResponse]
