"""Environment-driven settings for the audit service.

As in the items service, configuration comes exclusively from environment
variables, so no secret is embedded in the codebase, and values are validated at
process start to fail fast on misconfiguration.
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

    app_name: str = "audit-service"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Database per service: the audit history lives in its own database with its
    # own credential, so neither service can read or change the other's data and
    # each schema evolves independently.
    mongodb_uri: SecretStr
    mongodb_db_name: str = "audit"
    mongodb_server_selection_timeout_ms: int = Field(default=5000, ge=1)
    mongodb_connect_timeout_ms: int = Field(default=10000, ge=1)
    mongodb_socket_timeout_ms: int = Field(default=10000, ge=1)

    # Event consumption. The durable consumer name identifies this service to
    # JetStream, which tracks its acknowledgement position across restarts and
    # spreads messages across replicas.
    nats_url: str = "nats://nats:4222"
    consumer_enabled: bool = True
    consumer_durable_name: str = "audit-service"
    consumer_batch_size: int = Field(default=50, ge=1, le=500)
    consumer_max_deliver: int = Field(default=5, ge=1)
    consumer_ack_wait_seconds: float = Field(default=30.0, gt=0.0)

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _ALLOWED_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_ALLOWED_LOG_LEVELS)}")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
