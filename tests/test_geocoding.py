"""Fallback geocoding when Nominatim is blocked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions import DataUnavailableError, HttpRequestError
from app.core.http import AsyncHttpClient
from app.models.location import LocationData
from app.services.external.geocoding import FallbackGeocoder
from app.services.external.nominatim import NominatimClient
from app.services.external.open_meteo import OpenMeteoClient


def _open_meteo_geocode_payload() -> dict:
    return {
        "results": [
            {
                "id": 1,
                "name": "Kalyanpur",
                "latitude": 26.513,
                "longitude": 80.249,
                "admin1": "Uttar Pradesh",
                "admin2": "Kanpur Nagar",
                "country": "India",
                "country_code": "in",
            }
        ]
    }


@pytest.mark.asyncio
async def test_open_meteo_geocode() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search")
        assert "Kalyanpur" in str(request.url)
        return httpx.Response(200, json=_open_meteo_geocode_payload())

    raw = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = AsyncHttpClient(client=raw, timeout=5.0)
    client = OpenMeteoClient(
        http,
        geocoding_base_url="https://geocoding.example.test/v1",
    )
    async with http:
        location = await client.geocode("Kalyanpur, Kanpur")

    assert location.latitude == pytest.approx(26.513)
    assert location.longitude == pytest.approx(80.249)
    assert location.source == "open-meteo"
    assert "Kalyanpur" in location.display_name


@pytest.mark.asyncio
async def test_fallback_geocoder_uses_open_meteo_after_nominatim_403() -> None:
    nominatim = AsyncMock(spec=NominatimClient)
    nominatim.geocode = AsyncMock(
        side_effect=HttpRequestError(
            "Upstream returned HTTP 403",
            provider="nominatim",
            status_code=403,
        )
    )
    open_meteo = AsyncMock(spec=OpenMeteoClient)
    open_meteo.geocode = AsyncMock(
        return_value=LocationData(
            latitude=26.513,
            longitude=80.249,
            display_name="Kalyanpur, Uttar Pradesh, India",
            source="open-meteo",
        )
    )

    geocoder = FallbackGeocoder(nominatim, open_meteo)
    location = await geocoder.geocode("Kalyanpur, Kanpur")

    assert location.source == "open-meteo"
    open_meteo.geocode.assert_awaited_once()


@pytest.mark.asyncio
async def test_fallback_geocoder_does_not_call_open_meteo_on_success() -> None:
    nominatim = AsyncMock(spec=NominatimClient)
    nominatim.geocode = AsyncMock(
        return_value=LocationData(
            latitude=26.513,
            longitude=80.249,
            display_name="Kalyanpur, Kanpur",
        )
    )
    open_meteo = AsyncMock(spec=OpenMeteoClient)
    open_meteo.geocode = AsyncMock()

    geocoder = FallbackGeocoder(nominatim, open_meteo)
    location = await geocoder.geocode("Kalyanpur, Kanpur")

    assert location.source == "nominatim"
    open_meteo.geocode.assert_not_called()


@pytest.mark.asyncio
async def test_open_meteo_geocode_no_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    raw = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = AsyncHttpClient(client=raw, timeout=5.0)
    client = OpenMeteoClient(
        http,
        geocoding_base_url="https://geocoding.example.test/v1",
    )
    async with http:
        with pytest.raises(DataUnavailableError):
            await client.geocode("Nowhere Land XYZ")
