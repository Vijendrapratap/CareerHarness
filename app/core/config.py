"""Application configuration using Pydantic Settings."""

import base64
import os
import secrets
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "CareerHarness"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Host & Ports
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Master KMS / Encryption key (32 bytes base64-encoded for AES-256)
    # Default is generated on first load for local dev/testing if not specified
    MASTER_KEY: str = os.getenv(
        "CAREER_HARNESS_MASTER_KEY",
        base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    )

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./career_harness.db",
    )
    DB_ECHO: bool = False

    # Redis / Celery
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def REDIS_URL(self) -> str:
        proto = "redis"
        return os.getenv("REDIS_URL", f"{proto}://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}")

    # Rate limits & Guardrails
    MAX_ROLES_PER_TENANT: int = 3
    MGMT_ROLE_EXTRA_SLOT: int = 1
    TRUSTED_MODE_MAX_APPLIES_PER_DAY: int = 10
    MIN_READINESS_SCORE_FOR_SCOUT: int = 70


settings = Settings()
