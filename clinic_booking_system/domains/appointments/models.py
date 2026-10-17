#domains/appointments/models.py

"""
Domain models for appointments

Plain  representing core domain entities.
No FastAPI, Python dataclasses, Pydantic, 
Decided to use sqlalchemy's MappedAsDataclass due to its low overhead and native support 
for ORM relationship --ditched python dataclasses since Mapped uses it under the hood
Relationships:
    One patient can book multiple appointments but each appointment belongs to exacly one patient
    One doctor can attend to multiple appointments but each appointment can be attended by one doctor

"""

# domains/appointments/models.py
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clinic_booking_system.database.db import Base

if TYPE_CHECKING:
    from clinic_booking_system.domains.doctors.models import Doctor
    from clinic_booking_system.domains.patients.models import Patient
 



# -------------------------------------------------- domains/appointments/models.py
class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("status IN ('booked','cancelled')", name="ck_appointments_status"),
        CheckConstraint(
            "status = 'booked' OR (cancellation_reason IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_appointments_cancel_fields",
        ),
        # The exclusivity guarantee: one *booked* appointment per doctor per slot.
        Index(
            "uq_appointments_doctor_start_booked",
            "doctor_id",
            "start_time",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_patient_start", "patient_id", "start_time"),
    )
    # Make server-generated timestamps available right after flush (important for async).
    __mapper_args__ = {"eager_defaults": True}
 
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # always UTC-aware
 
    status: Mapped[str] = mapped_column(String(20), default="booked")
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
 
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
 
    doctor: Mapped["Doctor"] = relationship(
        back_populates="appointments", init=False, repr=False
    )
    patient: Mapped["Patient"] = relationship(
        back_populates="appointments", init=False, repr=False
    )