# database/session.py
"""Async SQLAlchemy engine and per-request session dependency (README §12).

The engine is created lazily on first use so that importing this module
does not immediately read settings or require a database (which would break
test collection when ``DATABASE_URL`` is not set in the environment).

A new ``AsyncSession`` is yielded for every request and closed (and rolled
back if still open) when the request finishes.

Usage in a router::

    async def my_endpoint(session: AsyncSession = Depends(get_session)):
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and return the sessionmaker, reading settings on first call."""
    from clinic_booking_system.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        # Echo SQL only in local/debug mode, not in production.
        echo=(settings.APP_ENV == "local"),
        future=True,
        # poolclass=NullPool, i added this after  integration tests failed. use in testing, avoid in production
    )
    return async_sessionmaker(
        engine,
        # expire_on_commit=False keeps ORM objects usable after commit in
        # async code (avoids lazy-load errors when attributes are accessed
        # post-commit).
        expire_on_commit=False,
        class_=AsyncSession,
    )


# Module-level holder; populated on first call to get_session.
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield one ``AsyncSession`` per request.

    Commits are the service's responsibility. This dependency only ensures
    the session is closed (and the transaction rolled back if open) when the
    request completes, even if an exception escapes the service layer.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = _make_session_factory()
    async with _session_factory() as session:
        yield session
