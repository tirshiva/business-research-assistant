"""Optional live integration tests for external APIs.

Enable with:

    RUN_INTEGRATION_TESTS=true uv run pytest -m integration
"""

from __future__ import annotations

import pytest

from app.core.cache import InMemoryCache
from app.core.http import AsyncHttpClient
from app.models.location import LocationData
from app.models.weather import WeatherData
from app.services.external import NominatimClient, OpenMeteoClient
from tests.conftest import require_integration_tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_geocode_and_forecast() -> None:
    """Geocode a real Indian address and fetch a validated weather forecast."""
    require_integration_tests()

    async with AsyncHttpClient(timeout=30.0) as http:
        cache = InMemoryCache(default_ttl_seconds=60)
        nominatim = NominatimClient(
            http,
            user_agent="IndiaBusinessResearchDecisionAgent/0.1 (integration-tests)",
            cache=cache,
            min_request_interval_seconds=1.0,
        )
        open_meteo = OpenMeteoClient(http, cache=cache)

        location = await nominatim.geocode("Sector 62, Noida")
        weather = await open_meteo.get_forecast(
            latitude=location.latitude,
            longitude=location.longitude,
        )

    assert isinstance(location, LocationData)
    assert location.latitude != 0
    assert location.longitude != 0
    assert "Noida" in location.display_name or "noida" in location.display_name.lower()

    assert isinstance(weather, WeatherData)
    assert weather.current is not None or weather.hourly or weather.daily
