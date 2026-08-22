"""Application-level weather models (provider-agnostic)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class CurrentWeather(BaseModel):
    """Current weather conditions at a location."""

    observed_at: datetime | None = None
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    apparent_temperature_c: float | None = None
    precipitation_mm: float | None = None
    weather_code: int | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    cloud_cover_pct: float | None = None


class HourlyWeather(BaseModel):
    """Hourly weather observation or forecast point."""

    time: datetime
    temperature_c: float | None = None
    relative_humidity_pct: float | None = None
    precipitation_mm: float | None = None
    precipitation_probability_pct: float | None = None
    weather_code: int | None = None
    wind_speed_kmh: float | None = None
    cloud_cover_pct: float | None = None


class DailyWeather(BaseModel):
    """Daily weather aggregation."""

    date: date
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    precipitation_sum_mm: float | None = None
    weather_code: int | None = None
    wind_speed_max_kmh: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None


class WeatherData(BaseModel):
    """Normalized weather payload returned by the Open-Meteo client."""

    latitude: float
    longitude: float
    timezone: str | None = None
    elevation_m: float | None = None
    current: CurrentWeather | None = None
    hourly: list[HourlyWeather] = Field(default_factory=list)
    daily: list[DailyWeather] = Field(default_factory=list)
    source: str = "open-meteo"
