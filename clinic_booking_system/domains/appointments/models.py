# domains/appointments/models.py
"""
Persistence model for appointments (README §11).

SQLAlchemy's MappedAsDataclass is used for its low overhead and native support
for ORM relationships (Mapped already builds on dataclasses). This is the
persistence layer only: the API contract lives in schemas.py.

Relationships:
    One patient can book many appointments; each appointment has exactly one patient.
    One doctor can attend many appointments; each appointment has exactly one doctor.

The 30-minute duration is a code constant (scheduling.SLOT_MINUTES), so no end_time is stored.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clinic_booking_system.database.db import Base

if TYPE_CHECKING:
    from clinic_booking_system.domains.doctors.models import Doctor
    from clinic_booking_system.domains.patients.models import Patient

STATUS_BOOKED = "booked"
STATUS_CANCELLED = "cancelled"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            f"status IN ('{STATUS_BOOKED}','{STATUS_CANCELLED}')",
            name="ck_appointments_status",
        ),
        CheckConstraint(
            f"status = '{STATUS_BOOKED}' OR "
            "(cancellation_reason IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_appointments_cancel_fields",
        ),
        # The exclusivity guarantee: one *booked* appointment per doctor per slot.
        Index(
            "uq_appointments_doctor_start_booked",
            "doctor_id",
            "start_time",
            unique=True,
            postgresql_where=text(f"status = '{STATUS_BOOKED}'"),
        ),
        Index("ix_appointments_patient_start", "patient_id", "start_time"),
    )
    # Server-generated timestamps are available right after flush (important for async).
    __mapper_args__= {"eager_defaults": True}

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT")
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT")
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )  # always UTC-aware

    status: Mapped[str] = mapped_column(String(20), default=STATUS_BOOKED)
    # 500 chars to match the API limit (README §13.3); was 255.
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(
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
