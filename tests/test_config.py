"""Tests for application configuration loading."""

import pytest

from app.config.settings import Settings, get_settings


def test_settings_load_from_environment(settings_env: None) -> None:
    """Settings should reflect values provided via environment variables."""
    settings = get_settings()
    assert settings.app_name == "Test App"
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.database_url == (
        "postgresql+asyncpg://test:test@localhost:5432/testdb"
    )
    assert settings.open_meteo_base_url == "https://example.test/v1"
    assert settings.nominatim_base_url == "https://nominatim.example.test"
    assert settings.nominatim_user_agent == "TestAgent/0.1 (tests@example.com)"
    assert settings.http_timeout_seconds == 5.0


def test_settings_defaults_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should fall back to safe defaults when env vars are unset."""
    for key in (
        "APP_NAME",
        "APP_ENV",
        "LOG_LEVEL",
        "DATABASE_URL",
        "OPEN_METEO_BASE_URL",
        "OPEN_METEO_ARCHIVE_BASE_URL",
        "NOMINATIM_BASE_URL",
        "NOMINATIM_USER_AGENT",
        "HTTP_TIMEOUT_SECONDS",
        "CACHE_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    get_settings.cache_clear()
    settings = Settings(_env_file=None)

    assert settings.app_name == "India Business Research & Decision Agent"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert "postgresql" in settings.database_url
    assert settings.open_meteo_base_url == "https://api.open-meteo.com/v1"
    assert settings.nominatim_base_url == "https://nominatim.openstreetmap.org"
    assert "IndiaBusinessResearchDecisionAgent" in settings.nominatim_user_agent


def test_get_settings_is_cached(settings_env: None) -> None:
    """get_settings should return the same cached instance."""
    first = get_settings()
    second = get_settings()
    assert first is second
