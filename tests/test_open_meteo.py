"""Unit tests for the Open-Meteo client using mocked HTTP responses."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.core.cache import InMemoryCache
from app.core.exceptions import (
    DataUnavailableError,
    ExternalTimeoutError,
    HttpRequestError,
    MalformedResponseError,
    RateLimitError,
)
from app.core.http import AsyncHttpClient
from app.models.weather import WeatherData
from app.services.external.open_meteo import OpenMeteoClient


def _forecast_payload() -> dict:
    return {
        "latitude": 28.62,
        "longitude": 77.36,
        "timezone": "Asia/Kolkata",
        "elevation": 200.0,
        "current": {
            "time": "2024-06-01T12:00",
            "temperature_2m": 34.5,
            "relative_humidity_2m": 55,
            "apparent_temperature": 37.0,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.3,
            "wind_direction_10m": 180,
            "cloud_cover": 40,
        },
        "hourly": {
            "time": ["2024-06-01T12:00", "2024-06-01T13:00"],
            "temperature_2m": [34.5, 35.1],
            "relative_humidity_2m": [55, 52],
            "precipitation": [0.0, 0.1],
            "weather_code": [1, 2],
            "wind_speed_10m": [12.3, 11.0],
            "cloud_cover": [40, 45],
        },
        "daily": {
            "time": ["2024-06-01"],
            "temperature_2m_max": [36.0],
            "temperature_2m_min": [28.0],
            "precipitation_sum": [1.2],
            "weather_code": [2],
            "wind_speed_10m_max": [18.0],
            "sunrise": ["2024-06-01T05:20"],
            "sunset": ["2024-06-01T19:05"],
        },
    }


def _build_client(
    handler: httpx.MockTransport | httpx.AsyncBaseTransport,
    *,
    cache: InMemoryCache | None = None,
) -> tuple[OpenMeteoClient, AsyncHttpClient]:
    raw = httpx.AsyncClient(
        transport=handler,
        base_url="https://example.test",
    )
    http = AsyncHttpClient(client=raw, timeout=5.0)
    client = OpenMeteoClient(
        http,
        forecast_base_url="https://example.test/v1",
        archive_base_url="https://archive.example.test/v1",
        cache=cache or InMemoryCache(default_ttl_seconds=60),
        cache_ttl_seconds=60,
    )
    return client, http


@pytest.mark.asyncio
async def test_successful_weather_forecast() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        assert "/v1/forecast" in str(request.url)
        return httpx.Response(200, json=_forecast_payload())

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        weather = await client.get_forecast(latitude=28.62, longitude=77.36)

    assert isinstance(weather, WeatherData)
    assert weather.latitude == 28.62
    assert weather.longitude == 77.36
    assert weather.current is not None
    assert weather.current.temperature_c == 34.5
    assert len(weather.hourly) == 2
    assert len(weather.daily) == 1
    assert weather.daily[0].date == date(2024, 6, 1)
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_weather_cache_behavior() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_forecast_payload())

    cache = InMemoryCache(default_ttl_seconds=60)
    client, http = _build_client(httpx.MockTransport(handler), cache=cache)
    async with http:
        first = await client.get_current_weather(28.62, 77.36)
        second = await client.get_current_weather(28.62, 77.36)

    assert first.model_dump() == second.model_dump()
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_weather_api_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(HttpRequestError) as exc_info:
            await client.get_forecast(28.62, 77.36)

    assert exc_info.value.status_code == 500
    assert exc_info.value.provider == "open-meteo"


@pytest.mark.asyncio
async def test_weather_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(RateLimitError):
            await client.get_hourly_forecast(28.62, 77.36)


@pytest.mark.asyncio
async def test_weather_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(ExternalTimeoutError):
            await client.get_daily_forecast(28.62, 77.36)


@pytest.mark.asyncio
async def test_weather_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(MalformedResponseError):
            await client.get_forecast(28.62, 77.36)


@pytest.mark.asyncio
async def test_weather_provider_error_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": True, "reason": "Latitude out of range"},
        )

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(DataUnavailableError):
            await client.get_forecast(999.0, 77.36)


@pytest.mark.asyncio
async def test_historical_weather_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/v1/archive" in str(request.url)
        payload = _forecast_payload()
        payload.pop("current")
        return httpx.Response(200, json=payload)

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        weather = await client.get_historical_weather(
            28.62,
            77.36,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
        )

    assert weather.current is None
    assert weather.hourly
    assert weather.daily
