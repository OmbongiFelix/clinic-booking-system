# domains/doctors/models.py
"""
Domain models for appointments

Plain  representing core domain entities.
No FastAPI, Python dataclasses, Pydantic,
Decided to use sqlalchemy's MappedAsDataclass due to its low overhead and native support
for ORM relationship --ditched python dataclasses since Mapped uses it under the hood
"""

# domains/doctors/models.py
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clinic_booking_system.database.db import Base

if TYPE_CHECKING:
    from clinic_booking_system.domains.appointments.models import Appointment


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    fullname: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    working_hours: Mapped[list["DoctorWorkingHours"]] = relationship(
        back_populates="doctor", init=False, repr=False, default_factory=list
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor", init=False, repr=False, default_factory=list
    )


class DoctorWorkingHours(Base):
    __tablename__ = "doctor_working_hours"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "weekday", name="uq_working_hours_doctor_weekday"
        ),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_hours_weekday"),
        CheckConstraint("start_time < end_time", name="ck_working_hours_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    weekday: Mapped[int]  # 0 = Monday
    # Time of day in the clinic's local timezone (not an instant), so plain Time.
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    doctor: Mapped["Doctor"] = relationship(
        back_populates="working_hours", init=False, repr=False
    )
