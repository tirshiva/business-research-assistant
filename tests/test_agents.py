"""Unit tests for research agents with mocked upstream clients."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agents.competition import CompetitionAgent, CompetitionAgentInput
from app.agents.geography import GeographyAgent, GeographyAgentInput
from app.agents.government import GovernmentDataAgent, GovernmentDataAgentInput
from app.agents.weather import WeatherAgent, WeatherAgentInput
from app.core.exceptions import DataUnavailableError, HttpRequestError
from app.models.location import LocationData
from app.models.weather import CurrentWeather, DailyWeather, HourlyWeather, WeatherData
from app.services.external.business_search import BusinessListing
from app.services.external.government_data import GovernmentDatasetMetadata


def _sample_weather() -> WeatherData:
    return WeatherData(
        latitude=28.62,
        longitude=77.36,
        timezone="Asia/Kolkata",
        current=CurrentWeather(
            observed_at=datetime(2024, 6, 1, 12, 0),
            temperature_c=34.5,
            relative_humidity_pct=55,
            precipitation_mm=0.0,
            weather_code=1,
            wind_speed_kmh=12.3,
            wind_direction_deg=180,
        ),
        hourly=[
            HourlyWeather(
                time=datetime(2024, 6, 1, 12, 0),
                temperature_c=34.5,
                relative_humidity_pct=55,
                precipitation_mm=0.0,
                precipitation_probability_pct=20,
                weather_code=1,
                wind_speed_kmh=12.3,
            )
        ],
        daily=[
            DailyWeather(
                date=date(2024, 6, 1),
                temperature_max_c=36.0,
                temperature_min_c=28.0,
                precipitation_sum_mm=1.2,
                weather_code=2,
                wind_speed_max_kmh=18.0,
            )
        ],
    )


@pytest.mark.asyncio
async def test_weather_agent_completed() -> None:
    open_meteo = AsyncMock()
    open_meteo.get_forecast = AsyncMock(return_value=_sample_weather())
    agent = WeatherAgent(open_meteo)

    result = await agent.run(
        WeatherAgentInput(
            location="Sector 62, Noida",
            latitude=28.62,
            longitude=77.36,
            forecast_days=3,
        )
    )

    assert result.agent == "weather"
    assert result.status == "completed"
    assert result.confidence > 0
    assert result.findings
    assert result.sources
    assert "open_meteo.get_forecast" in result.allowed_tools
    current = result.findings[0].data
    assert current["temperature_c"] == 34.5
    assert "humidity_pct" in current
    assert "wind_speed_kmh" in current


@pytest.mark.asyncio
async def test_weather_agent_surfaces_api_failure() -> None:
    open_meteo = AsyncMock()
    open_meteo.get_forecast = AsyncMock(
        side_effect=HttpRequestError("boom", provider="open-meteo", status_code=500)
    )
    agent = WeatherAgent(open_meteo)

    result = await agent.run(
        WeatherAgentInput(location="Noida", latitude=28.6, longitude=77.3)
    )

    assert result.status == "failed"
    assert result.confidence == 0.0
    assert result.errors
    assert result.findings == []


@pytest.mark.asyncio
async def test_geography_agent_completed() -> None:
    nominatim = AsyncMock()
    nominatim.geocode = AsyncMock(
        return_value=LocationData(
            latitude=28.628,
            longitude=77.365,
            display_name="Sector 62, Noida, Uttar Pradesh, India",
            importance=0.5,
            address={
                "suburb": "Sector 62",
                "city": "Noida",
                "state": "Uttar Pradesh",
                "country": "India",
            },
            bounding_box=["28.61", "28.64", "77.35", "77.38"],
        )
    )
    agent = GeographyAgent(nominatim)

    result = await agent.run(
        GeographyAgentInput(
            location="Sector 62, Noida",
            reference_latitude=28.61,
            reference_longitude=77.35,
        )
    )

    assert result.agent == "geography"
    assert result.status == "completed"
    assert result.findings
    coords = result.findings[0].data["coordinates"]
    assert coords["latitude"] == pytest.approx(28.628)
    assert result.findings[0].data["distance_km_from_reference"] is not None


@pytest.mark.asyncio
async def test_geography_agent_data_unavailable() -> None:
    nominatim = AsyncMock()
    nominatim.geocode = AsyncMock(
        side_effect=DataUnavailableError("not found", provider="nominatim")
    )
    agent = GeographyAgent(nominatim)

    result = await agent.run(GeographyAgentInput(location="Nowhere Land XYZ"))

    assert result.status == "data_unavailable"
    assert result.confidence == 0.0
    assert result.errors


@pytest.mark.asyncio
async def test_competition_agent_completed() -> None:
    provider = AsyncMock()
    provider.name = "overpass"
    provider.search_nearby = AsyncMock(
        return_value=[
            BusinessListing(
                name="Demo Kitchen",
                category="restaurant",
                latitude=28.629,
                longitude=77.366,
                address="Sector 62",
                distance_km=0.25,
                source="overpass",
                source_url="https://www.openstreetmap.org/node/1",
            )
        ]
    )
    agent = CompetitionAgent(provider)

    result = await agent.run(
        CompetitionAgentInput(
            business_type="cloud kitchen",
            location="Sector 62, Noida",
            latitude=28.628,
            longitude=77.365,
        )
    )

    assert result.agent == "competition"
    assert result.status == "completed"
    assert len(result.findings) == 1
    data = result.findings[0].data
    assert data["business_name"] == "Demo Kitchen"
    assert data["category"] == "restaurant"
    assert data["distance_km"] == 0.25
    assert data["source"] == "overpass"


@pytest.mark.asyncio
async def test_competition_agent_unavailable() -> None:
    provider = AsyncMock()
    provider.name = "overpass"
    provider.search_nearby = AsyncMock(
        side_effect=DataUnavailableError("none", provider="overpass")
    )
    agent = CompetitionAgent(provider)

    result = await agent.run(
        CompetitionAgentInput(
            business_type="cafe",
            location="Noida",
            latitude=28.6,
            longitude=77.3,
        )
    )

    assert result.status == "data_unavailable"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_government_data_agent_completed() -> None:
    provider = AsyncMock()
    provider.name = "data.gov.in"
    provider.search = AsyncMock(
        return_value=[
            GovernmentDatasetMetadata(
                id="abc",
                title="Noida municipal licenses",
                notes="Public license metadata",
                organization="Example Org",
                source_url="https://data.gov.in/dataset/example",
                resources=[{"id": "r1", "format": "CSV", "url": "https://example"}],
                tags=["noida", "license"],
            )
        ]
    )
    agent = GovernmentDataAgent(provider)

    result = await agent.run(
        GovernmentDataAgentInput(
            query="food business license",
            location="Noida",
            business_type="cloud kitchen",
        )
    )

    assert result.agent == "government_data"
    assert result.status == "completed"
    assert result.findings[0].data["dataset_id"] == "abc"
    assert result.sources[0].name == "data.gov.in"


@pytest.mark.asyncio
async def test_government_data_agent_structured_unavailable() -> None:
    provider = AsyncMock()
    provider.name = "data.gov.in"
    provider.search = AsyncMock(
        side_effect=DataUnavailableError(
            "catalog unavailable",
            provider="data.gov.in",
            status_code=503,
        )
    )
    agent = GovernmentDataAgent(provider)

    result = await agent.run(GovernmentDataAgentInput(query="zoning"))

    assert result.status == "data_unavailable"
    assert result.confidence == 0.0
    assert result.findings
    assert result.findings[0].data["reason"] == "data_unavailable"
    assert "catalog unavailable" in result.errors[0]


def test_agent_input_validation() -> None:
    with pytest.raises(ValidationError):
        GeographyAgentInput()

    with pytest.raises(ValidationError):
        WeatherAgentInput(
            location="Noida",
            latitude=28.6,
            longitude=77.3,
            start_date=date(2024, 6, 2),
            end_date=date(2024, 6, 1),
        )


@pytest.mark.asyncio
async def test_agents_do_not_include_recommendations() -> None:
    open_meteo = AsyncMock()
    open_meteo.get_forecast = AsyncMock(return_value=_sample_weather())
    result = await WeatherAgent(open_meteo).run(
        WeatherAgentInput(location="Noida", latitude=28.6, longitude=77.3)
    )
    dumped: dict[str, Any] = result.model_dump()
    assert "recommendation" not in dumped
    assert "opportunity_score" not in dumped
    text = str(dumped).lower()
    assert "you should open" not in text
