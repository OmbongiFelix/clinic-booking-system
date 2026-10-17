# core/config.py
"""Centralized runtime configuration, read once from the environment.

The rest of the codebase calls ``get_settings()``; nothing else reads env vars.
"""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: str = "local"  # README §20
    LOG_LEVEL: str = "INFO"

    # Required: no default, so a missing value fails at startup.
    DATABASE_URL: str

    # Scheduling rules (README A1, A5). No booking horizon (A12).
    CLINIC_TIMEZONE: str = "Africa/Nairobi"
    MIN_BOOKING_LEAD_MINUTES: int = Field(default=60, ge=0)

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Render supplies postgres:// or postgresql://; SQLAlchemy async needs +asyncpg (README §12)."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @field_validator("CLINIC_TIMEZONE")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {v!r}") from exc
        return v

    @property
    def clinic_tz(self) -> ZoneInfo:
        return ZoneInfo(self.CLINIC_TIMEZONE)


@lru_cache
def get_settings() -> Settings:
    """Cached singleton. Import this, not Settings."""
    return Settings()