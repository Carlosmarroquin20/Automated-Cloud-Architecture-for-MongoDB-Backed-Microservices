"""Environment-driven application settings.

Configuration is sourced exclusively from environment variables to satisfy the
zero-trust requirement that no secret is embedded in the codebase. Values are
validated at process start to fail fast on misconfiguration.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service identity and runtime selectors.
    app_name: str = "mongodb-microservice"
    app_env: str = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # MongoDB Atlas connection. The URI is credential-bearing and is wrapped in
    # SecretStr to prevent accidental disclosure through logs or error output.
    mongodb_uri: SecretStr
    mongodb_db_name: str
    mongodb_max_pool_size: int = Field(default=50, ge=1)
    mongodb_min_pool_size: int = Field(default=0, ge=0)
    mongodb_server_selection_timeout_ms: int = Field(default=5000, ge=1)
    mongodb_connect_timeout_ms: int = Field(default=10000, ge=1)
    mongodb_socket_timeout_ms: int = Field(default=10000, ge=1)

    # Startup connectivity warm-up. Disabling the ping supports hermetic test
    # execution without a reachable database.
    mongodb_ping_on_startup: bool = True
    mongodb_connect_max_retries: int = Field(default=5, ge=0)
    mongodb_connect_retry_base_delay_seconds: float = Field(default=0.5, ge=0.0)

    # Cross-origin policy. Empty by default to enforce a restrictive posture;
    # allowed origins are supplied explicitly per environment.
    cors_allow_origins: str = ""

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _ALLOWED_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_ALLOWED_LOG_LEVELS)}")
        return normalized

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    # Cached to guarantee a single validated configuration instance per process.
    return Settings()
