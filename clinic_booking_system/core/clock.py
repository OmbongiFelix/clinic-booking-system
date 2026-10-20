# core/clock.py
"""Injectable "now" (a FastAPI dependency).

Routers take ``now: datetime = Depends(get_now)``. Tests override it with
``app.dependency_overrides[get_now] = lambda: fixed_datetime`` so time rules
(past, lead time, already started) are deterministic.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_now() -> datetime:
    """FastAPI dependency: the current timezone-aware UTC time."""
    return utc_now()
