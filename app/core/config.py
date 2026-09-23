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

    # OpenRouter API Key
    OPENROUTER_API_KEY: str = ""

    # Mailbox OAuth apps (Google Cloud / Azure). Redirect URI to register with each provider:
    #   {APP_BASE_URL}/api/emails/oauth/{gmail|outlook}/callback
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    APP_BASE_URL: str = "http://127.0.0.1:3000"  # public URL of the frontend

    # Browser auto-fill. Submitting is OFF unless explicitly enabled: approving then only fills and
    # validates the form ("dry run"). Turn on per environment once you trust it.
    APPLY_SUBMIT_ENABLED: bool = False
    APPLY_DAILY_CAP: int = 10
    APPLY_ARTIFACT_DIR: str = "var/apply"  # screenshots and resume files handed to the browser

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

    # JWT & Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "career-harness-jwt-secret-key-32charsmin-for-security")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days session

    # Rate limits & Guardrails
    MAX_ROLES_PER_TENANT: int = 3
    MGMT_ROLE_EXTRA_SLOT: int = 1
    TRUSTED_MODE_MAX_APPLIES_PER_DAY: int = 10
    MIN_READINESS_SCORE_FOR_SCOUT: int = 70


settings = Settings()
