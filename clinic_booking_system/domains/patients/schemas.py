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


class PatientAppointmentsRequest(BaseModel):
    """Request body for booking an appointment"""

    patient_id: int


class PatientAppointmentsResponse(BaseModel):
    """Response body for confirmed booking"""
    appointments: dict



