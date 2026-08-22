"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the application.

    Values are loaded from environment variables and an optional ``.env`` file.
    Secrets must never be hardcoded.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "India Business Research & Decision Agent"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/ibrda"

    # External APIs
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    open_meteo_archive_base_url: str = "https://archive-api.open-meteo.com/v1"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = (
        "IndiaBusinessResearchDecisionAgent/0.1 (contact@example.com)"
    )
    overpass_base_url: str = "https://overpass-api.de/api/interpreter"
    data_gov_in_base_url: str = "https://data.gov.in/api/3/action"
    data_gov_in_api_key: str = ""

    # HTTP / cache
    http_timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 600
    nominatim_cache_ttl_seconds: int = 86400
    nominatim_min_request_interval_seconds: float = 1.0

    # LLM / planner
    llm_provider: Literal["local", "bedrock"] = "local"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.0
    planner_max_retries: int = 2
    planner_retry_backoff_seconds: float = 0.25
    bedrock_region: str = "ap-south-1"
    bedrock_model_id: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
