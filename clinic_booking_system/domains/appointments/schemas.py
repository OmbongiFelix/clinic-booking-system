#appointments/schemas.py
"""
Pydantic request/response contracts for the public API.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from clinic_booking_system.core.config import get_settings


class AppointmentRequest(BaseModel):
    """Request body for booking an appointment"""

    patient_id: int
    doctor_id: int
    start_time: datetime

class AppointmentCancellationRequest(BaseModel):
    """Request body of cancelling an appointment"""
    id: int
    reason: str | None = Field(..., max_length=1500)

class AppointmentBookedResponse(BaseModel):
    """Response body for confirmed booking"""
    id: int
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime

class AppointmentReschedullingRequest(BaseModel):
    """Request body for rescheduling and appointment"""
    id: int
    doctor_id: int
    start_time: datetime = Field(..., description="Future start time for the appointment")




