"""Tests for application startup."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_returns_fastapi_instance(settings_env: None) -> None:
    """Application factory should produce a FastAPI instance."""
    application = create_app()
    assert isinstance(application, FastAPI)
    assert application.title == "Test App"


def test_application_starts_successfully(client: TestClient) -> None:
    """Application should start and serve the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "Test App"
    assert "/health" in payload["paths"]
