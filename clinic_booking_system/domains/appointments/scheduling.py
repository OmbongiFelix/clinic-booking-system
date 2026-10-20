# domains/appointments/scheduling.py
"""Pure scheduling rules: no database, no clock, no FastAPI.

Generates slots for a date and validates a start time against working hours,
the 30-minute grid, the past, and the minimum lead time (README A3, A5, A6).
"Now" is always passed in, so every rule is unit-testable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from clinic_booking_system.core.errors import (
    SlotInPast,
    SlotMisaligned,
    SlotOutsideWorkingHours,
    SlotTooSoon,
)

SLOT_MINUTES = 30
SLOT_DURATION = timedelta(minutes=SLOT_MINUTES)


class WorkingHoursLike(Protocol):
    """Shape of a doctor's working-hours row (weekday 0 = Monday)."""

    weekday: int
    start_time: time
    end_time: time


@dataclass(frozen=True)
class WorkingBlock:
    start: time
    end: time


@dataclass(frozen=True)
class Slot:
    start_time: datetime
    end_time: datetime


def block_for_weekday(
    working_hours: Iterable[WorkingHoursLike], weekday: int
) -> WorkingBlock | None:
    for row in working_hours:
        if row.weekday == weekday:
            return WorkingBlock(row.start_time, row.end_time)
    return None


def slot_end(start: datetime) -> datetime:
    return start + SLOT_DURATION


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def is_aligned(start: datetime, tz: ZoneInfo) -> bool:
    local = start.astimezone(tz)
    return (
        local.minute % SLOT_MINUTES == 0
        and local.second == 0
        and local.microsecond == 0
    )


def day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) of a clinic-local calendar day, as UTC instants."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def generate_slots(day: date, block: WorkingBlock, tz: ZoneInfo) -> list[Slot]:
    """All 30-minute slots that fit inside the block on ``day`` (clinic local)."""
    cursor = datetime.combine(day, block.start, tzinfo=tz).astimezone(UTC)
    close = datetime.combine(day, block.end, tzinfo=tz).astimezone(UTC)
    slots: list[Slot] = []
    while cursor + SLOT_DURATION <= close:
        slots.append(
            Slot(cursor.astimezone(tz), (cursor + SLOT_DURATION).astimezone(tz))
        )
        cursor += SLOT_DURATION
    return slots


def validate_start_time(
    start: datetime,
    *,
    working_hours: Iterable[WorkingHoursLike],
    now: datetime,
    lead_minutes: int,
    tz: ZoneInfo,
) -> None:
    """Raise a domain error if ``start`` cannot be booked. Order follows README §13.1:
    alignment -> working hours -> past -> lead time. "Already taken" is the database's call."""
    _require_aware(start, "start")
    _require_aware(now, "now")

    if not is_aligned(start, tz):
        raise SlotMisaligned(details={"start_time": start.isoformat()})

    local_start = start.astimezone(tz)
    local_end = slot_end(start).astimezone(tz)
    block = block_for_weekday(working_hours, local_start.weekday())
    if (
        block is None
        or local_end.date() != local_start.date()
        or local_start.time() < block.start
        or local_end.time() > block.end
    ):
        raise SlotOutsideWorkingHours(details={"start_time": start.isoformat()})

    if start < now:
        raise SlotInPast(details={"start_time": start.isoformat()})
    if start < now + timedelta(minutes=lead_minutes):
        raise SlotTooSoon(
            message=f"Appointments must be booked at least {lead_minutes} minutes ahead.",
            details={"start_time": start.isoformat(), "lead_minutes": lead_minutes},
        )


def available_slots(
    day: date,
    *,
    working_hours: Iterable[WorkingHoursLike],
    booked_starts: Iterable[datetime],
    now: datetime,
    lead_minutes: int,
    tz: ZoneInfo,
) -> list[Slot]:
    """Free slots for a day: hours -> grid -> drop past/too-soon -> drop booked (A6, A7).
    A non-working day or a past date simply yields an empty list."""
    block = block_for_weekday(working_hours, day.weekday())
    if block is None:
        return []
    earliest = now + timedelta(minutes=lead_minutes)
    taken = set(booked_starts)
    return [
        s
        for s in generate_slots(day, block, tz)
        if s.start_time >= earliest and s.start_time not in taken
    ]
