r"""Settings from environment


Centralized runtime configuration for the Locus service.

Reads environment variables once into a cached Settings object so the
rest of the codebase never calls python-dotenv directly.
"""

"""Centralized runtime configuration, read once from the environment."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"

    # Required: no default, so a missing value fails at startup.
    DATABASE_URL: str

    # Scheduling rules
    CLINIC_TIMEZONE: str = "Africa/Nairobi"
    MIN_BOOKING_LEAD_MINUTES: int = Field(default=60, ge=0)
    BOOKING_HORIZON_DAYS: int = Field(default=30, ge=1)

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