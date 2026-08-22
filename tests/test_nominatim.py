"""Unit tests for the Nominatim client using mocked HTTP responses."""

from __future__ import annotations

import httpx
import pytest

from app.core.cache import InMemoryCache
from app.core.exceptions import (
    DataUnavailableError,
    ExternalTimeoutError,
    HttpRequestError,
    MalformedResponseError,
)
from app.core.http import AsyncHttpClient
from app.models.location import LocationData
from app.services.external.nominatim import NominatimClient


def _geocode_payload() -> list[dict]:
    return [
        {
            "place_id": 123,
            "licence": "Data © OpenStreetMap contributors",
            "osm_type": "way",
            "osm_id": 456,
            "lat": "28.6280",
            "lon": "77.3649",
            "display_name": "Sector 62, Noida, Uttar Pradesh, India",
            "importance": 0.5,
            "boundingbox": ["28.61", "28.64", "77.35", "77.38"],
            "address": {
                "suburb": "Sector 62",
                "city": "Noida",
                "state": "Uttar Pradesh",
                "country": "India",
            },
        }
    ]


def _reverse_payload() -> dict:
    return {
        "place_id": 123,
        "lat": "28.6280",
        "lon": "77.3649",
        "display_name": "Sector 62, Noida, Uttar Pradesh, India",
        "address": {
            "suburb": "Sector 62",
            "city": "Noida",
            "state": "Uttar Pradesh",
            "country": "India",
        },
    }


def _build_client(
    handler: httpx.AsyncBaseTransport,
    *,
    cache: InMemoryCache | None = None,
) -> tuple[NominatimClient, AsyncHttpClient]:
    raw = httpx.AsyncClient(transport=handler)
    http = AsyncHttpClient(client=raw, timeout=5.0)
    client = NominatimClient(
        http,
        base_url="https://nominatim.example.test",
        user_agent="TestAgent/0.1 (tests@example.com)",
        cache=cache or InMemoryCache(default_ttl_seconds=60),
        cache_ttl_seconds=60,
        min_request_interval_seconds=0.0,
    )
    return client, http


@pytest.mark.asyncio
async def test_successful_geocoding() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search")
        assert request.headers.get("User-Agent") == "TestAgent/0.1 (tests@example.com)"
        return httpx.Response(200, json=_geocode_payload())

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        location = await client.geocode("Sector 62, Noida")

    assert isinstance(location, LocationData)
    assert location.latitude == pytest.approx(28.6280)
    assert location.longitude == pytest.approx(77.3649)
    assert "Noida" in location.display_name
    assert location.address["city"] == "Noida"


@pytest.mark.asyncio
async def test_successful_reverse_geocoding() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/reverse")
        return httpx.Response(200, json=_reverse_payload())

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        location = await client.reverse_geocode(28.6280, 77.3649)

    assert location.display_name.startswith("Sector 62")
    assert location.latitude == pytest.approx(28.6280)


@pytest.mark.asyncio
async def test_geocode_cache_behavior() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_geocode_payload())

    cache = InMemoryCache(default_ttl_seconds=60)
    client, http = _build_client(httpx.MockTransport(handler), cache=cache)
    async with http:
        first = await client.geocode("Sector 62, Noida")
        second = await client.geocode("Sector 62, Noida")

    assert first.model_dump() == second.model_dump()
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_geocode_api_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(HttpRequestError) as exc_info:
            await client.geocode("Sector 62, Noida")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_geocode_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(ExternalTimeoutError):
            await client.geocode("Sector 62, Noida")


@pytest.mark.asyncio
async def test_geocode_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "object"})

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(MalformedResponseError):
            await client.geocode("Sector 62, Noida")


@pytest.mark.asyncio
async def test_geocode_no_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client, http = _build_client(httpx.MockTransport(handler))
    async with http:
        with pytest.raises(DataUnavailableError):
            await client.geocode("Somewhere that does not exist xyz")
