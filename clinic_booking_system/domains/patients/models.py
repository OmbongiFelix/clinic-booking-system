#domains/patients/models.py

# domains/patients/models.py
from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from clinic_booking_system.database.db import Base

if TYPE_CHECKING:
    from clinic_booking_system.domains.appointments.models import Appointment
 

# This does not avoid circular import at runtime; only used by IDEs/Mypy
if TYPE_CHECKING:
    # Keep this here ONLY for IDE autocomplete/type checking
    from clinic_booking_system.domains.appointments.models import Appointment

class Patient(Base):
    __tablename__ = "patients"
 
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    fullname: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str] = mapped_column(String(255))
 
    appointments: Mapped[List["Appointment"]] = relationship(
        back_populates="patient", init=False, repr=False, default_factory=list
    )