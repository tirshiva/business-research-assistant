"""Unit tests for Overpass and data.gov.in providers."""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import DataUnavailableError
from app.core.http import AsyncHttpClient
from app.services.external.government_data import DataGovInProvider
from app.services.external.overpass import OverpassBusinessSearchProvider


def _http_client(handler: httpx.MockTransport) -> AsyncHttpClient:
    return AsyncHttpClient(client=httpx.AsyncClient(transport=handler))


@pytest.mark.asyncio
async def test_overpass_maps_listings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 28.629,
                        "lon": 77.366,
                        "tags": {
                            "name": "Test Cafe",
                            "amenity": "cafe",
                            "addr:city": "Noida",
                        },
                    }
                ]
            },
        )

    async with _http_client(httpx.MockTransport(handler)) as http:
        provider = OverpassBusinessSearchProvider(http)
        listings = await provider.search_nearby(
            business_type="cafe",
            latitude=28.628,
            longitude=77.365,
            radius_km=1.0,
            limit=5,
        )

    assert len(listings) == 1
    assert listings[0].name == "Test Cafe"
    assert listings[0].category == "cafe"
    assert listings[0].distance_km is not None


@pytest.mark.asyncio
async def test_data_gov_in_search_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "package_search" in str(request.url)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "results": [
                        {
                            "id": "ds-1",
                            "name": "sample-dataset",
                            "title": "Sample Dataset",
                            "notes": "About sample data",
                            "organization": {"title": "MoSPI"},
                            "resources": [
                                {
                                    "id": "r1",
                                    "name": "csv",
                                    "format": "CSV",
                                    "url": "https://example/file.csv",
                                }
                            ],
                            "tags": [{"name": "noida"}],
                        }
                    ]
                },
            },
        )

    async with _http_client(httpx.MockTransport(handler)) as http:
        provider = DataGovInProvider(http)
        results = await provider.search("noida license", limit=3)

    assert len(results) == 1
    assert results[0].title == "Sample Dataset"
    assert results[0].organization == "MoSPI"


@pytest.mark.asyncio
async def test_data_gov_in_unavailable_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    async with _http_client(httpx.MockTransport(handler)) as http:
        provider = DataGovInProvider(http)
        with pytest.raises(DataUnavailableError):
            await provider.search("anything")
