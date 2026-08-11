"""Settings validation and derivation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_REQUIRED = {"mongodb_uri": "mongodb://localhost:27017", "mongodb_db_name": "example"}


def test_log_level_is_normalized_to_upper_case() -> None:
    settings = Settings(**_REQUIRED, log_level="debug")
    assert settings.log_level == "DEBUG"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_REQUIRED, log_level="verbose")


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(**_REQUIRED, cors_allow_origins="https://a.example, https://b.example ,")
    assert settings.cors_allow_origins_list == ["https://a.example", "https://b.example"]


def test_empty_cors_origins_yield_no_entries() -> None:
    settings = Settings(**_REQUIRED, cors_allow_origins="")
    assert settings.cors_allow_origins_list == []


def test_production_flag_is_case_insensitive() -> None:
    settings = Settings(**_REQUIRED, app_env="Production")
    assert settings.is_production is True


def test_uri_is_wrapped_as_secret() -> None:
    settings = Settings(**_REQUIRED)
    # The credential-bearing URI must not be exposed by the default representation.
    assert "mongodb://localhost:27017" not in repr(settings)
    assert settings.mongodb_uri.get_secret_value() == "mongodb://localhost:27017"
