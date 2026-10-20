"""Alembic migration environment for the Clinic Booking System.

Configures Alembic to use the SQLAlchemy async engine from
``database.session`` and the shared ``Base.metadata`` from all ORM models.
``models_registry`` is imported first so every model class is registered
with ``Base.metadata`` before ``target_metadata`` is read.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

# ── Register all ORM models so their tables appear in Base.metadata ─────────
import clinic_booking_system.database.models_registry  # noqa: F401
from alembic import context
from clinic_booking_system.core.config import get_settings
from clinic_booking_system.database.db import Base

# Alembic Config object (gives access to values in alembic.ini).
config = context.config

# Set up Python logging from alembic.ini if the file has a [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata Alembic compares against to generate auto-migrations.
target_metadata = Base.metadata


def get_url() -> str:
    """Read DATABASE_URL from the application settings (not alembic.ini)."""
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations without a live database connection.

    Outputs the SQL to stdout so it can be reviewed or applied manually.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute pending migrations using an existing synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, obtain a sync connection, and run migrations."""
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live database)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
