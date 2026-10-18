# ── Build stage ──────────────────────────────────────────────────────────────
# Use uv to resolve and install dependencies in a reproducible way.
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy only the lockfile and project metadata first so Docker can cache the
# dependency-install layer when only source files change.
COPY pyproject.toml uv.lock ./

# Install all dependencies (including dev? No — only the main group here).
RUN uv sync --locked --no-dev --no-install-project

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Create a non-root user for security (README §18.1).
RUN useradd --create-home --shell /bin/bash clinic
USER clinic
WORKDIR /home/clinic/app

# Copy the installed virtual environment from the builder.
COPY --from=builder --chown=clinic:clinic /app/.venv ./.venv

# Copy source and migration files.
COPY --chown=clinic:clinic clinic_booking_system ./clinic_booking_system
COPY --chown=clinic:clinic alembic ./alembic
COPY --chown=clinic:clinic alembic.ini ./

# Make uv and the venv available on PATH.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
ENV PATH="/home/clinic/app/.venv/bin:$PATH"

# Run Alembic migrations then start the server.
# Migrations at container start are acceptable for a single instance (README §18.1).
CMD ["sh", "-c", "alembic upgrade head && uvicorn clinic_booking_system.main:app --host 0.0.0.0 --port 8000"]
