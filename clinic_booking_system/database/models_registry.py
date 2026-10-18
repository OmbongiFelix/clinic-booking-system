# database/models_registry.py
from clinic_booking_system.domains.appointments.models import Appointment  # noqa: F401
from clinic_booking_system.domains.doctors.models import Doctor, DoctorWorkingHours  # noqa: F401
from clinic_booking_system.domains.patients.models import Patient  # noqa: F401