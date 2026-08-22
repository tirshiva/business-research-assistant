"""Weather research agent powered by Open-Meteo."""

from __future__ import annotations

from datetime import date
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from app.agents.base import ResearchAgent
from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.core.exceptions import DataUnavailableError, ExternalServiceError
from app.services.external.open_meteo import OpenMeteoClient

# WMO Weather interpretation codes (Open-Meteo).
_WEATHER_CODE_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


class WeatherAgentInput(BaseModel):
    """Input schema for the weather agent."""

    location: str = Field(..., min_length=1)
    latitude: float
    longitude: float
    start_date: date | None = None
    end_date: date | None = None
    forecast_days: int = Field(default=7, ge=1, le=16)

    @model_validator(mode="after")
    def validate_time_range(self) -> WeatherAgentInput:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class WeatherAgent(ResearchAgent):
    """Collect weather observations/forecasts for a location."""

    name: ClassVar[str] = "weather"
    allowed_tools: ClassVar[list[str]] = [
        "open_meteo.get_forecast",
        "open_meteo.get_historical_weather",
    ]

    def __init__(self, open_meteo: OpenMeteoClient) -> None:
        self._open_meteo = open_meteo

    async def run(self, payload: WeatherAgentInput) -> AgentResult:
        self._log_start(payload)
        errors: list[str] = []
        sources: list[AgentSource] = []
        findings: list[AgentFinding] = []

        try:
            weather = await self._fetch_weather(payload)
        except DataUnavailableError as exc:
            return AgentResult(
                agent="weather",
                findings=[],
                sources=[],
                confidence=0.0,
                status="data_unavailable",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )
        except ExternalServiceError as exc:
            return AgentResult(
                agent="weather",
                findings=[],
                sources=[],
                confidence=0.0,
                status="failed",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )

        sources.append(
            AgentSource(
                name="Open-Meteo",
                url="https://open-meteo.com/",
                tool="open_meteo",
                notes=f"timezone={weather.timezone}",
            )
        )

        current_data = _current_payload(weather.current)
        if current_data:
            findings.append(
                AgentFinding(
                    title=f"Current weather — {payload.location}",
                    summary=_summarize_current(payload.location, current_data),
                    data=current_data,
                    confidence=0.9,
                )
            )

        hourly_slice = weather.hourly[:24]
        if hourly_slice:
            precip_probs = [
                point.precipitation_probability_pct
                for point in hourly_slice
                if point.precipitation_probability_pct is not None
            ]
            findings.append(
                AgentFinding(
                    title="Next 24h hourly outlook",
                    summary=(
                        f"{len(hourly_slice)} hourly points for {payload.location}; "
                        f"max precip probability "
                        f"{max(precip_probs) if precip_probs else 'n/a'}%."
                    ),
                    data={
                        "hours": [
                            {
                                "time": point.time.isoformat(),
                                "temperature_c": point.temperature_c,
                                "precipitation_mm": point.precipitation_mm,
                                "precipitation_probability_pct": (
                                    point.precipitation_probability_pct
                                ),
                                "wind_speed_kmh": point.wind_speed_kmh,
                                "humidity_pct": point.relative_humidity_pct,
                                "condition": _condition_label(point.weather_code),
                            }
                            for point in hourly_slice
                        ]
                    },
                    confidence=0.85,
                )
            )

        if weather.daily:
            findings.append(
                AgentFinding(
                    title="Daily forecast summary",
                    summary=f"{len(weather.daily)} daily aggregates available.",
                    data={
                        "days": [
                            {
                                "date": day.date.isoformat(),
                                "temperature_max_c": day.temperature_max_c,
                                "temperature_min_c": day.temperature_min_c,
                                "precipitation_sum_mm": day.precipitation_sum_mm,
                                "wind_speed_max_kmh": day.wind_speed_max_kmh,
                                "condition": _condition_label(day.weather_code),
                            }
                            for day in weather.daily
                        ]
                    },
                    confidence=0.8,
                )
            )

        if not findings:
            errors.append("Weather API returned no usable observations")
            status = "data_unavailable"
            confidence = 0.0
        else:
            status = "completed"
            confidence = min(0.95, 0.7 + 0.05 * len(findings))

        return AgentResult(
            agent="weather",
            findings=findings,
            sources=sources,
            confidence=confidence,
            status=status,
            errors=errors,
            allowed_tools=list(self.allowed_tools),
        )

    async def _fetch_weather(self, payload: WeatherAgentInput) -> Any:
        today = date.today()
        if payload.start_date and payload.end_date and payload.end_date < today:
            return await self._open_meteo.get_historical_weather(
                payload.latitude,
                payload.longitude,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )

        forecast_days = payload.forecast_days
        if payload.start_date and payload.end_date:
            forecast_days = max(
                1,
                min(16, (payload.end_date - payload.start_date).days + 1),
            )
        elif payload.end_date:
            forecast_days = max(1, min(16, (payload.end_date - today).days + 1))

        return await self._open_meteo.get_forecast(
            payload.latitude,
            payload.longitude,
            forecast_days=forecast_days,
        )


def _current_payload(current: Any) -> dict[str, Any] | None:
    if current is None:
        return None
    return {
        "temperature_c": current.temperature_c,
        "precipitation_mm": current.precipitation_mm,
        "precipitation_probability_pct": None,
        "wind_speed_kmh": current.wind_speed_kmh,
        "wind_direction_deg": current.wind_direction_deg,
        "humidity_pct": current.relative_humidity_pct,
        "condition": _condition_label(current.weather_code),
        "observed_at": (
            current.observed_at.isoformat() if current.observed_at else None
        ),
    }


def _summarize_current(location: str, data: dict[str, Any]) -> str:
    temp = data.get("temperature_c")
    condition = data.get("condition") or "Unknown conditions"
    humidity = data.get("humidity_pct")
    wind = data.get("wind_speed_kmh")
    return (
        f"{location}: {condition}; "
        f"temp={temp}°C, humidity={humidity}%, wind={wind} km/h."
    )


def _condition_label(code: int | None) -> str | None:
    if code is None:
        return None
    return _WEATHER_CODE_LABELS.get(code, f"Weather code {code}")
