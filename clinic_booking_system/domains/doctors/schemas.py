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


class DoctorAvailabilityRequest(BaseModel):
    """Request body for booking an appointment"""

    doctor_id: int
    date: datetime = Field(..., description="The date that you want to check the doctor's availability")

class DoctorAvailabilityResponse(BaseModel):
    """Response body for confirmed booking"""
    doctor_id: int
    date: datetime
    timezone: str
    slots: dict
    



