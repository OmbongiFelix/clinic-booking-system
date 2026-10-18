
# ── Build stage ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install production dependencies into /app/.venv
RUN uv sync --locked --no-dev --no-install-project

# ── Runtime stage ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN useradd --create-home --shell /bin/bash clinic

WORKDIR /app

# Preserve the exact virtual-environment path from the builder.
COPY --from=builder --chown=clinic:clinic /app/.venv /app/.venv

# Copy application and migration files.
COPY --chown=clinic:clinic clinic_booking_system ./clinic_booking_system
COPY --chown=clinic:clinic alembic ./alembic
COPY --chown=clinic:clinic alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER clinic

# Run migrations, then launch FastAPI.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn clinic_booking_system.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
