# tests/unit/test_scheduling.py
"""Unit tests for ``domains/appointments/scheduling.py`` (README §17).

These tests exercise *all* pure scheduling functions without a database.
"Now" is always passed in explicitly so time-dependent rules are
deterministic and do not flake based on when the suite is run.

Test cases from the design's minimum case list (README §17):
- Slot generation: happy path, non-working day.
- Alignment check: aligned / misaligned.
- Working-hours fit: valid slot, slot outside, non-working weekday.
- Past and lead-time: past, inside lead time, exactly at boundary, future.
- Available slots: filtering of past/too-soon/booked slots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from clinic_booking_system.core.errors import (
    SlotInPast,
    SlotMisaligned,
    SlotOutsideWorkingHours,
    SlotTooSoon,
)
from clinic_booking_system.domains.appointments.scheduling import (
    SLOT_MINUTES,
    WorkingBlock,
    available_slots,
    block_for_weekday,
    day_bounds_utc,
    generate_slots,
    is_aligned,
    validate_start_time,
)

TZ = ZoneInfo("Africa/Nairobi")  # UTC+3
LEAD = 60  # minutes


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


@dataclass
class _Hours:
    """Minimal working-hours stub that satisfies the WorkingHoursLike protocol."""

    weekday: int
    start_time: time
    end_time: time


def _mon_fri_hours():
    """Return Mon–Fri 09:00–17:00 working hours."""
    return [_Hours(wd, time(9, 0), time(17, 0)) for wd in range(5)]


def _aware(year, month, day, hour, minute, tz=TZ) -> datetime:
    """Shorthand for a timezone-aware datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=tz)


# ---------------------------------------------------------------------------
# generate_slots
# ---------------------------------------------------------------------------


class TestGenerateSlots:
    """Tests for generate_slots: verifies 30-minute grid within a block."""

    def test_happy_path_count(self):
        """09:00–17:00 → 16 slots of 30 minutes each."""
        block = WorkingBlock(time(9, 0), time(17, 0))
        slots = generate_slots(date(2026, 10, 20), block, TZ)  # Tuesday
        assert len(slots) == 16

    def test_first_slot(self):
        block = WorkingBlock(time(9, 0), time(17, 0))
        slots = generate_slots(date(2026, 10, 20), block, TZ)
        assert slots[0].start_time.hour == 9
        assert slots[0].start_time.minute == 0

    def test_last_slot_ends_at_close(self):
        block = WorkingBlock(time(9, 0), time(17, 0))
        slots = generate_slots(date(2026, 10, 20), block, TZ)
        last = slots[-1]
        local_end = last.end_time.astimezone(TZ)
        assert local_end.time() == time(17, 0)

    def test_each_slot_is_30_minutes(self):
        block = WorkingBlock(time(9, 0), time(11, 0))
        slots = generate_slots(date(2026, 10, 20), block, TZ)
        for s in slots:
            assert s.end_time - s.start_time == timedelta(minutes=SLOT_MINUTES)

    def test_slots_are_timezone_aware(self):
        block = WorkingBlock(time(9, 0), time(10, 0))
        slots = generate_slots(date(2026, 10, 20), block, TZ)
        for s in slots:
            assert s.start_time.tzinfo is not None
            assert s.end_time.tzinfo is not None


# ---------------------------------------------------------------------------
# is_aligned
# ---------------------------------------------------------------------------


class TestIsAligned:
    def test_aligned_on_hour(self):
        dt = _aware(2026, 10, 20, 9, 0)
        assert is_aligned(dt, TZ) is True

    def test_aligned_on_half(self):
        dt = _aware(2026, 10, 20, 9, 30)
        assert is_aligned(dt, TZ) is True

    def test_misaligned_one_minute(self):
        dt = _aware(2026, 10, 20, 9, 1)
        assert is_aligned(dt, TZ) is False

    def test_misaligned_29_minutes(self):
        dt = _aware(2026, 10, 20, 9, 29)
        assert is_aligned(dt, TZ) is False


# ---------------------------------------------------------------------------
# block_for_weekday
# ---------------------------------------------------------------------------


class TestBlockForWeekday:
    def test_returns_block_for_working_day(self):
        block = block_for_weekday(_mon_fri_hours(), 0)  # Monday
        assert block is not None
        assert block.start == time(9, 0)
        assert block.end == time(17, 0)

    def test_returns_none_for_non_working_day(self):
        block = block_for_weekday(_mon_fri_hours(), 5)  # Saturday
        assert block is None


# ---------------------------------------------------------------------------
# day_bounds_utc
# ---------------------------------------------------------------------------


class TestDayBoundsUtc:
    def test_start_is_midnight_local(self):
        start, _ = day_bounds_utc(date(2026, 10, 20), TZ)
        local_start = start.astimezone(TZ)
        assert local_start.hour == 0
        assert local_start.minute == 0

    def test_end_is_next_midnight_local(self):
        _, end = day_bounds_utc(date(2026, 10, 20), TZ)
        local_end = end.astimezone(TZ)
        assert local_end.date() == date(2026, 10, 21)

    def test_results_are_utc_aware(self):
        start, end = day_bounds_utc(date(2026, 10, 20), TZ)
        assert start.tzinfo is not None
        assert end.tzinfo is not None


# ---------------------------------------------------------------------------
# validate_start_time
# ---------------------------------------------------------------------------

# "now" used throughout validation tests: 2026-10-20 08:00 local (Tue).
_NOW = _aware(2026, 10, 20, 8, 0)  # 30+ min before open (09:00)
_HOURS = _mon_fri_hours()


class TestValidateStartTime:
    def test_valid_slot(self):
        """A well-formed future slot should pass without raising."""
        start = _aware(2026, 10, 20, 10, 0)  # 10:00 Tue, 2 h after now
        validate_start_time(
            start, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
        )

    def test_misaligned_raises(self):
        start = _aware(2026, 10, 20, 10, 15)  # not on :00/:30
        with pytest.raises(SlotMisaligned):
            validate_start_time(
                start, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
            )

    def test_non_working_weekday_raises(self):
        start = _aware(2026, 10, 18, 10, 0)  # 2026-10-18 is a Sunday
        with pytest.raises(SlotOutsideWorkingHours):
            validate_start_time(
                start, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
            )

    def test_before_working_hours_raises(self):
        start = _aware(2026, 10, 20, 8, 30)  # before 09:00
        with pytest.raises(SlotOutsideWorkingHours):
            validate_start_time(
                start, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
            )

    def test_slot_ending_after_close_raises(self):
        """A slot starting at 16:45 would end at 17:15, outside hours."""
        start = _aware(2026, 10, 20, 16, 30)
        # slot ends at 17:00 — this is valid (slot_end <= close)
        validate_start_time(
            start, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
        )

        start_too_late = _aware(2026, 10, 20, 17, 0)
        # slot would end at 17:30 — outside hours
        with pytest.raises(SlotOutsideWorkingHours):
            validate_start_time(
                start_too_late, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
            )

    def test_past_start_raises_slot_in_past(self):
        past_now = _aware(2026, 10, 20, 12, 0)
        past_start = _aware(2026, 10, 20, 11, 0)  # an hour in the past
        with pytest.raises(SlotInPast):
            validate_start_time(
                past_start, working_hours=_HOURS, now=past_now, lead_minutes=LEAD, tz=TZ
            )

    def test_within_lead_time_raises_slot_too_soon(self):
        """A slot 30 minutes ahead when lead is 60 minutes → SlotTooSoon."""
        now = _aware(2026, 10, 20, 9, 0)
        start = _aware(2026, 10, 20, 9, 30)  # only 30 min ahead
        with pytest.raises(SlotTooSoon):
            validate_start_time(
                start, working_hours=_HOURS, now=now, lead_minutes=LEAD, tz=TZ
            )

    def test_exactly_at_lead_time_boundary_is_allowed(self):
        """A slot exactly ``lead_minutes`` ahead must be accepted (A5: boundary is inclusive)."""
        now = _aware(2026, 10, 20, 9, 0)
        start = _aware(2026, 10, 20, 10, 0)  # exactly 60 minutes ahead
        # Should not raise
        validate_start_time(
            start, working_hours=_HOURS, now=now, lead_minutes=LEAD, tz=TZ
        )

    def test_naive_start_raises_value_error(self):
        naive = datetime(2026, 10, 20, 10, 0)  # no tzinfo
        with pytest.raises(ValueError):
            validate_start_time(
                naive, working_hours=_HOURS, now=_NOW, lead_minutes=LEAD, tz=TZ
            )


# ---------------------------------------------------------------------------
# available_slots
# ---------------------------------------------------------------------------


class TestAvailableSlots:
    def _now(self):
        """'now' early on a Monday so all 09:00–17:00 slots are available."""
        return _aware(2026, 10, 19, 7, 0)  # 2026-10-19 is Monday

    def test_working_day_returns_slots(self):
        slots = available_slots(
            date(2026, 10, 19),
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=self._now(),
            lead_minutes=LEAD,
            tz=TZ,
        )
        assert len(slots) > 0

    def test_non_working_day_returns_empty(self):
        slots = available_slots(
            date(2026, 10, 18),  # Sunday
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=self._now(),
            lead_minutes=LEAD,
            tz=TZ,
        )
        assert slots == []

    def test_past_date_returns_empty(self):
        """A date entirely in the past returns no slots."""
        far_future_now = _aware(2026, 12, 31, 23, 0)
        slots = available_slots(
            date(2026, 10, 19),
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=far_future_now,
            lead_minutes=LEAD,
            tz=TZ,
        )
        assert slots == []

    def test_booked_start_is_excluded(self):
        day = date(2026, 10, 19)
        all_slots = available_slots(
            day,
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=self._now(),
            lead_minutes=LEAD,
            tz=TZ,
        )
        assert all_slots

        # Book the first slot
        booked = [all_slots[0].start_time]
        remaining = available_slots(
            day,
            working_hours=_mon_fri_hours(),
            booked_starts=booked,
            now=self._now(),
            lead_minutes=LEAD,
            tz=TZ,
        )
        assert len(remaining) == len(all_slots) - 1
        assert all_slots[0] not in remaining

    def test_too_soon_slots_excluded(self):
        """Slots within the lead-time window are filtered out."""
        # now = 09:30, lead = 60 min → earliest bookable is 10:30
        now = _aware(2026, 10, 19, 9, 30)
        slots = available_slots(
            date(2026, 10, 19),
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=now,
            lead_minutes=LEAD,
            tz=TZ,
        )
        for s in slots:
            assert s.start_time >= now + timedelta(minutes=LEAD)

    def test_slots_end_within_working_hours(self):
        """No slot should extend past the working-hours end time."""
        slots = available_slots(
            date(2026, 10, 19),
            working_hours=_mon_fri_hours(),
            booked_starts=[],
            now=self._now(),
            lead_minutes=LEAD,
            tz=TZ,
        )
        for s in slots:
            assert s.end_time.astimezone(TZ).time() <= time(17, 0)
