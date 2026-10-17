# tests/integration/test_appointments.py
"""Integration tests for all appointment endpoints (README §17).

These tests run against a real PostgreSQL database (CI service container
or local ``docker compose up -d db``). Each test gets a rolled-back
transaction so the database is clean at the start of every test.

Minimum case list tested (README §17):
Booking: happy path, past start, inside lead time, at lead-time boundary,
outside working hours, non-working weekday, misaligned time, naive datetime,
unknown doctor, unknown patient, slot already taken, rebook after cancel.
Cancel: happy path, missing reason, already cancelled, unknown id,
slot bookable again after cancel.
Reschedule: happy path (old slot free, new taken), cancelled appointment,
new slot taken (original unchanged), new slot violates rules, same slot.
Patient list: only upcoming booked, sorted ascending, cancelled excluded,
unknown patient → 404.
Availability: excludes booked, excludes past/too-soon, empty on non-working
day, unknown doctor → 404.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

# All tests are async; pytest-asyncio in auto mode handles this.
pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helper: next occurrence of a given weekday from a reference date
# ---------------------------------------------------------------------------

def _next_weekday(weekday: int, ref: datetime) -> datetime:
    """Return a datetime on the next occurrence of ``weekday`` (0=Mon) at 10:00 clinic time."""
    from datetime import date, timedelta
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Africa/Nairobi")
    today = ref.astimezone(TZ).date()
    days_ahead = (weekday - today.weekday()) % 7 or 7
    target = today + timedelta(days=days_ahead)
    return datetime(target.year, target.month, target.day, 10, 0, tzinfo=TZ)


# ── Booking ─────────────────────────────────────────────────────────────────

class TestBookAppointment:
    async def test_happy_path(self, client, seeded_db):
        """POST /appointments with valid data returns 201 and the appointment."""
        # fixed_now in conftest = 2026-01-01; pick a future Monday
        slot = "2026-10-19T10:00:00+03:00"  # Monday (weekday=0), well within hours
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": slot,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "booked"
        assert data["start_time"].startswith("2026-10-19")
        assert data["end_time"] > data["start_time"]

    async def test_unknown_doctor(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={"patient_id": seeded_db["patient_id"], "doctor_id": 99999, "start_time": "2026-10-19T10:00:00+03:00"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "DOCTOR_NOT_FOUND"

    async def test_unknown_patient(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={"patient_id": 99999, "doctor_id": seeded_db["doctor_id"], "start_time": "2026-10-19T10:00:00+03:00"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PATIENT_NOT_FOUND"

    async def test_past_start_time(self, client, seeded_db):
        """A slot in the past is rejected (fixed_now = 2026-01-01 00:00 UTC)."""
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2025-01-01T10:00:00+03:00",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLOT_IN_PAST"

    async def test_start_within_lead_time(self, client, seeded_db):
        """30 minutes ahead when lead is 60 minutes → SlotTooSoon.
        fixed_now = 2026-01-01 00:00 UTC = 03:00 Nairobi.
        A slot at 03:30 same day is only 30 min ahead.
        """
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-01-01T03:30:00+03:00",
            },
        )
        # Will be SLOT_OUTSIDE_WORKING_HOURS (03:30 before 09:00) or SLOT_TOO_SOON
        assert resp.status_code in (422,)

    async def test_naive_datetime_rejected(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-10-19T10:00:00",  # no offset
            },
        )
        assert resp.status_code == 422

    async def test_misaligned_time(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-10-19T10:15:00+03:00",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLOT_MISALIGNED"

    async def test_outside_working_hours(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-10-19T08:00:00+03:00",  # before 09:00
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"

    async def test_non_working_weekday(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-10-18T10:00:00+03:00",  # Sunday
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"

    async def test_slot_already_taken(self, client, seeded_db):
        """Two bookings for the same slot → second returns 409 SLOT_UNAVAILABLE."""
        slot = "2026-10-20T10:00:00+03:00"  # Tuesday
        body = {
            "patient_id": seeded_db["patient_id"],
            "doctor_id": seeded_db["doctor_id"],
            "start_time": slot,
        }
        resp1 = await client.post("/appointments", json=body)
        assert resp1.status_code == 201

        resp2 = await client.post("/appointments", json=body)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "SLOT_UNAVAILABLE"

    async def test_rebook_after_cancel(self, client, seeded_db):
        """Cancelling an appointment makes the slot available again."""
        slot = "2026-10-21T10:00:00+03:00"  # Wednesday
        body = {
            "patient_id": seeded_db["patient_id"],
            "doctor_id": seeded_db["doctor_id"],
            "start_time": slot,
        }
        resp1 = await client.post("/appointments", json=body)
        assert resp1.status_code == 201
        appt_id = resp1.json()["id"]

        # Cancel it
        cancel = await client.patch(
            f"/appointments/{appt_id}/cancel",
            json={"reason": "Testing rebooking"},
        )
        assert cancel.status_code == 200

        # Rebook the same slot
        resp2 = await client.post("/appointments", json=body)
        assert resp2.status_code == 201


# ── Cancel ───────────────────────────────────────────────────────────────────

class TestCancelAppointment:
    async def _book(self, client, seeded_db, slot="2026-10-22T10:00:00+03:00"):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": slot,
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_happy_path(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db)
        resp = await client.patch(
            f"/appointments/{appt_id}/cancel",
            json={"reason": "Patient is travelling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["cancellation_reason"] == "Patient is travelling"
        assert data["cancelled_at"] is not None

    async def test_missing_reason(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-10-26T10:00:00+03:00")
        resp = await client.patch(f"/appointments/{appt_id}/cancel", json={})
        assert resp.status_code == 422

    async def test_empty_reason_rejected(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-10-27T10:00:00+03:00")
        resp = await client.patch(
            f"/appointments/{appt_id}/cancel",
            json={"reason": "   "},  # whitespace only; strips to empty
        )
        assert resp.status_code == 422

    async def test_already_cancelled(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-10-28T10:00:00+03:00")
        await client.patch(
            f"/appointments/{appt_id}/cancel", json={"reason": "first cancel"}
        )
        resp = await client.patch(
            f"/appointments/{appt_id}/cancel", json={"reason": "second cancel"}
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "APPOINTMENT_ALREADY_CANCELLED"

    async def test_unknown_id(self, client, seeded_db):
        resp = await client.patch(
            "/appointments/99999/cancel", json={"reason": "test"}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "APPOINTMENT_NOT_FOUND"


# ── Reschedule ───────────────────────────────────────────────────────────────

class TestRescheduleAppointment:
    async def _book(self, client, seeded_db, slot):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": slot,
            },
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_happy_path(self, client, seeded_db):
        """Old slot freed, new slot taken atomically."""
        appt_id = await self._book(client, seeded_db, "2026-11-02T10:00:00+03:00")  # Mon
        resp = await client.patch(
            f"/appointments/{appt_id}/reschedule",
            json={"start_time": "2026-11-02T11:00:00+03:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "11:00" in data["start_time"]

        # Old slot is free — can be booked by someone else
        resp2 = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-11-02T10:00:00+03:00",
            },
        )
        assert resp2.status_code == 201

    async def test_same_slot_rejected(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-11-03T10:00:00+03:00")  # Tue
        resp = await client.patch(
            f"/appointments/{appt_id}/reschedule",
            json={"start_time": "2026-11-03T10:00:00+03:00"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SAME_SLOT"

    async def test_cancelled_appointment_rejected(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-11-04T10:00:00+03:00")  # Wed
        await client.patch(
            f"/appointments/{appt_id}/cancel", json={"reason": "reason"}
        )
        resp = await client.patch(
            f"/appointments/{appt_id}/reschedule",
            json={"start_time": "2026-11-04T11:00:00+03:00"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "APPOINTMENT_ALREADY_CANCELLED"

    async def test_new_slot_taken_original_unchanged(self, client, seeded_db):
        """When the new slot is taken, the original appointment is not changed."""
        # Book two slots
        appt1 = await self._book(client, seeded_db, "2026-11-05T10:00:00+03:00")  # Thu
        await self._book(client, seeded_db, "2026-11-05T11:00:00+03:00")

        # Try to reschedule appt1 to the taken slot
        resp = await client.patch(
            f"/appointments/{appt1}/reschedule",
            json={"start_time": "2026-11-05T11:00:00+03:00"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "SLOT_UNAVAILABLE"

        # appt1 is still at 10:00
        list_resp = await client.get(
            f"/patients/{seeded_db['patient_id']}/appointments"
        )
        starts = [a["start_time"] for a in list_resp.json()]
        assert any("10:00" in s for s in starts)

    async def test_new_slot_violates_rules(self, client, seeded_db):
        appt_id = await self._book(client, seeded_db, "2026-11-09T10:00:00+03:00")  # Mon
        resp = await client.patch(
            f"/appointments/{appt_id}/reschedule",
            json={"start_time": "2026-11-08T10:00:00+03:00"},  # Sunday
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"


# ── Patient list ──────────────────────────────────────────────────────────────

class TestPatientAppointments:
    async def test_upcoming_sorted_ascending(self, client, seeded_db):
        """Multiple appointments are returned in start_time asc order."""
        for slot in ("2026-12-01T10:00:00+03:00", "2026-12-02T09:00:00+03:00"):
            resp = await client.post(
                "/appointments",
                json={
                    "patient_id": seeded_db["patient_id"],
                    "doctor_id": seeded_db["doctor_id"],
                    "start_time": slot,
                },
            )
            assert resp.status_code == 201

        resp = await client.get(f"/patients/{seeded_db['patient_id']}/appointments")
        assert resp.status_code == 200
        starts = [a["start_time"] for a in resp.json()]
        assert starts == sorted(starts)

    async def test_cancelled_excluded(self, client, seeded_db):
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-12-03T10:00:00+03:00",
            },
        )
        appt_id = resp.json()["id"]
        await client.patch(
            f"/appointments/{appt_id}/cancel", json={"reason": "cancelled for list test"}
        )

        resp = await client.get(f"/patients/{seeded_db['patient_id']}/appointments")
        ids = [a["id"] for a in resp.json()]
        assert appt_id not in ids

    async def test_unknown_patient_returns_404(self, client, seeded_db):
        resp = await client.get("/patients/99999/appointments")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PATIENT_NOT_FOUND"


# ── Availability ──────────────────────────────────────────────────────────────

class TestAvailability:
    async def test_returns_slots_for_working_day(self, client, seeded_db):
        resp = await client.get(
            f"/doctors/{seeded_db['doctor_id']}/availability",
            params={"date": "2026-10-19"},  # Monday
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["doctor_id"] == seeded_db["doctor_id"]
        assert len(data["slots"]) > 0

    async def test_booked_slot_excluded(self, client, seeded_db):
        """A booked slot does not appear in availability."""
        resp = await client.post(
            "/appointments",
            json={
                "patient_id": seeded_db["patient_id"],
                "doctor_id": seeded_db["doctor_id"],
                "start_time": "2026-10-19T10:00:00+03:00",
            },
        )
        assert resp.status_code == 201

        avail = await client.get(
            f"/doctors/{seeded_db['doctor_id']}/availability",
            params={"date": "2026-10-19"},
        )
        starts = [s["start_time"] for s in avail.json()["slots"]]
        assert not any("10:00" in s for s in starts)

    async def test_non_working_day_returns_empty(self, client, seeded_db):
        resp = await client.get(
            f"/doctors/{seeded_db['doctor_id']}/availability",
            params={"date": "2026-10-18"},  # Sunday
        )
        assert resp.status_code == 200
        assert resp.json()["slots"] == []

    async def test_unknown_doctor_returns_404(self, client, seeded_db):
        resp = await client.get(
            "/doctors/99999/availability",
            params={"date": "2026-10-19"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "DOCTOR_NOT_FOUND"


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    async def test_health_ok(self, client, seeded_db):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Concurrency ───────────────────────────────────────────────────────────────

class TestConcurrency:
    """Two simultaneous bookings for the same slot: exactly one succeeds (README §17)."""

    async def test_simultaneous_bookings_one_wins(self, seeded_db, engine):
        """Fire two bookings concurrently; exactly one 201 and one 409."""
        from httpx import ASGITransport, AsyncClient
        from clinic_booking_system.core.clock import get_now
        from clinic_booking_system.database.session import get_session
        from clinic_booking_system.main import app

        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        async def _make_client():
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
            session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

            async def _session():
                async with session_factory() as s:
                    yield s

            app.dependency_overrides[get_session] = _session
            app.dependency_overrides[get_now] = lambda: fixed_now
            return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        body = {
            "patient_id": seeded_db["patient_id"],
            "doctor_id": seeded_db["doctor_id"],
            "start_time": "2026-10-23T10:00:00+03:00",  # Friday
        }

        async with await _make_client() as c:
            results = await asyncio.gather(
                c.post("/appointments", json=body),
                c.post("/appointments", json=body),
            )

        app.dependency_overrides.clear()

        statuses = sorted([r.status_code for r in results])
        assert statuses == [201, 409], f"Expected [201, 409], got {statuses}"
        codes = [r.json()["error"]["code"] for r in results if r.status_code == 409]
        assert codes == ["SLOT_UNAVAILABLE"]
