"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.config import get_settings
from app.core.cache import InMemoryCache
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger, setup_logging
from app.services.external import NominatimClient, OpenMeteoClient

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks for startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info(
        "Starting %s (env=%s)",
        settings.app_name,
        settings.app_env,
    )

    http_client = AsyncHttpClient(timeout=settings.http_timeout_seconds)
    cache = InMemoryCache(default_ttl_seconds=settings.cache_ttl_seconds)
    open_meteo = OpenMeteoClient(
        http_client,
        forecast_base_url=settings.open_meteo_base_url,
        archive_base_url=settings.open_meteo_archive_base_url,
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    nominatim = NominatimClient(
        http_client,
        base_url=settings.nominatim_base_url,
        user_agent=settings.nominatim_user_agent,
        cache=cache,
        cache_ttl_seconds=settings.nominatim_cache_ttl_seconds,
        min_request_interval_seconds=settings.nominatim_min_request_interval_seconds,
    )

    app.state.http_client = http_client
    app.state.cache = cache
    app.state.open_meteo = open_meteo
    app.state.nominatim = nominatim

    try:
        yield
    finally:
        await http_client.aclose()
        logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    setup_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
