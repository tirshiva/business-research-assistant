"""Shared pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import create_app


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic settings for tests."""
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///:memory:",
    )
    monkeypatch.setenv("OPEN_METEO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv(
        "OPEN_METEO_ARCHIVE_BASE_URL",
        "https://archive.example.test/v1",
    )
    monkeypatch.setenv("NOMINATIM_BASE_URL", "https://nominatim.example.test")
    monkeypatch.setenv(
        "NOMINATIM_USER_AGENT",
        "TestAgent/0.1 (tests@example.com)",
    )
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "60")
    get_settings.cache_clear()


@pytest.fixture
def client(settings_env: None) -> TestClient:
    """Return a TestClient bound to a freshly created application."""
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    get_settings.cache_clear()


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: live external API tests (enable with RUN_INTEGRATION_TESTS=true)",
    )


def require_integration_tests() -> None:
    """Skip the calling test unless live integration tests are enabled."""
    if os.getenv("RUN_INTEGRATION_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_INTEGRATION_TESTS=true to run live API tests")
