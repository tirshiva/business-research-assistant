"""Open-Meteo weather API client."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.core.cache import CacheBackend, InMemoryCache
from app.core.exceptions import DataUnavailableError, MalformedResponseError
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger
from app.models.weather import (
    CurrentWeather,
    DailyWeather,
    HourlyWeather,
    WeatherData,
)

logger = get_logger(__name__)

PROVIDER = "open-meteo"

DEFAULT_CURRENT = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover"
)
DEFAULT_HOURLY = (
    "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
    "weather_code,wind_speed_10m,cloud_cover"
)
ARCHIVE_HOURLY = (
    "temperature_2m,relative_humidity_2m,precipitation,"
    "weather_code,wind_speed_10m,cloud_cover"
)
DEFAULT_DAILY = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "weather_code,wind_speed_10m_max,sunrise,sunset"
)


class OpenMeteoClient:
    """Async client for Open-Meteo forecast and historical weather APIs."""

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        forecast_base_url: str = "https://api.open-meteo.com/v1",
        archive_base_url: str = "https://archive-api.open-meteo.com/v1",
        cache: CacheBackend | None = None,
        cache_ttl_seconds: int = 600,
    ) -> None:
        self._http = http_client
        self._forecast_base_url = forecast_base_url.rstrip("/")
        self._archive_base_url = archive_base_url.rstrip("/")
        self._cache: CacheBackend = cache or InMemoryCache(
            default_ttl_seconds=cache_ttl_seconds
        )
        self._cache_ttl_seconds = cache_ttl_seconds

    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        *,
        timezone: str = "auto",
    ) -> WeatherData:
        """Fetch current weather conditions for a coordinate."""
        return await self._forecast(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            include_current=True,
            include_hourly=False,
            include_daily=False,
            cache_prefix="current",
        )

    async def get_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        *,
        forecast_days: int = 7,
        timezone: str = "auto",
    ) -> WeatherData:
        """Fetch an hourly weather forecast for a coordinate."""
        return await self._forecast(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            forecast_days=forecast_days,
            include_current=False,
            include_hourly=True,
            include_daily=False,
            cache_prefix="hourly",
        )

    async def get_daily_forecast(
        self,
        latitude: float,
        longitude: float,
        *,
        forecast_days: int = 7,
        timezone: str = "auto",
    ) -> WeatherData:
        """Fetch a daily weather forecast for a coordinate."""
        return await self._forecast(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            forecast_days=forecast_days,
            include_current=False,
            include_hourly=False,
            include_daily=True,
            cache_prefix="daily",
        )

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        *,
        forecast_days: int = 7,
        timezone: str = "auto",
    ) -> WeatherData:
        """Fetch current, hourly, and daily forecast for a coordinate."""
        return await self._forecast(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            forecast_days=forecast_days,
            include_current=True,
            include_hourly=True,
            include_daily=True,
            cache_prefix="forecast",
        )

    async def get_historical_weather(
        self,
        latitude: float,
        longitude: float,
        *,
        start_date: date,
        end_date: date,
        timezone: str = "auto",
    ) -> WeatherData:
        """Fetch historical daily/hourly weather for a date range."""
        cache_key = (
            f"openmeteo:history:{latitude:.4f}:{longitude:.4f}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}:{timezone}"
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return WeatherData.model_validate(cached)

        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": timezone,
            "hourly": ARCHIVE_HOURLY,
            "daily": DEFAULT_DAILY,
        }
        payload = await self._http.get(
            f"{self._archive_base_url}/archive",
            params=params,
            provider=PROVIDER,
        )
        weather = self._parse_weather_payload(payload)
        await self._cache.set(
            cache_key,
            weather.model_dump(mode="json"),
            ttl_seconds=self._cache_ttl_seconds,
        )
        return weather

    async def _forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str,
        forecast_days: int = 7,
        include_current: bool,
        include_hourly: bool,
        include_daily: bool,
        cache_prefix: str,
    ) -> WeatherData:
        cache_key = (
            f"openmeteo:{cache_prefix}:{latitude:.4f}:{longitude:.4f}:"
            f"{forecast_days}:{timezone}"
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Open-Meteo cache hit for %s", cache_key)
            return WeatherData.model_validate(cached)

        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "forecast_days": forecast_days,
        }
        if include_current:
            params["current"] = DEFAULT_CURRENT
        if include_hourly:
            params["hourly"] = DEFAULT_HOURLY
        if include_daily:
            params["daily"] = DEFAULT_DAILY

        payload = await self._http.get(
            f"{self._forecast_base_url}/forecast",
            params=params,
            provider=PROVIDER,
        )
        weather = self._parse_weather_payload(payload)
        await self._cache.set(
            cache_key,
            weather.model_dump(mode="json"),
            ttl_seconds=self._cache_ttl_seconds,
        )
        return weather

    def _parse_weather_payload(self, payload: Any) -> WeatherData:
        if not isinstance(payload, dict):
            raise MalformedResponseError(
                "Open-Meteo response was not a JSON object",
                provider=PROVIDER,
            )

        if "error" in payload and payload.get("error"):
            raise DataUnavailableError(
                str(payload.get("reason") or "Open-Meteo reported an error"),
                provider=PROVIDER,
                details=str(payload),
            )

        try:
            latitude = float(payload["latitude"])
            longitude = float(payload["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedResponseError(
                "Open-Meteo response missing latitude/longitude",
                provider=PROVIDER,
                details=str(payload),
            ) from exc

        try:
            current = self._parse_current(payload.get("current"))
            hourly = self._parse_hourly(payload.get("hourly"))
            daily = self._parse_daily(payload.get("daily"))
            return WeatherData(
                latitude=latitude,
                longitude=longitude,
                timezone=payload.get("timezone"),
                elevation_m=_as_optional_float(payload.get("elevation")),
                current=current,
                hourly=hourly,
                daily=daily,
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise MalformedResponseError(
                "Failed to map Open-Meteo response into WeatherData",
                provider=PROVIDER,
                details=str(exc),
            ) from exc

    @staticmethod
    def _parse_current(raw: Any) -> CurrentWeather | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("current weather block must be an object")
        return CurrentWeather(
            observed_at=_parse_datetime(raw.get("time")),
            temperature_c=_as_optional_float(raw.get("temperature_2m")),
            relative_humidity_pct=_as_optional_float(raw.get("relative_humidity_2m")),
            apparent_temperature_c=_as_optional_float(raw.get("apparent_temperature")),
            precipitation_mm=_as_optional_float(raw.get("precipitation")),
            weather_code=_as_optional_int(raw.get("weather_code")),
            wind_speed_kmh=_as_optional_float(raw.get("wind_speed_10m")),
            wind_direction_deg=_as_optional_float(raw.get("wind_direction_10m")),
            cloud_cover_pct=_as_optional_float(raw.get("cloud_cover")),
        )

    @staticmethod
    def _parse_hourly(raw: Any) -> list[HourlyWeather]:
        if raw is None:
            return []
        if not isinstance(raw, dict):
            raise ValueError("hourly weather block must be an object")

        times = raw.get("time") or []
        if not isinstance(times, list):
            raise ValueError("hourly.time must be a list")

        points: list[HourlyWeather] = []
        for index, time_value in enumerate(times):
            observed_at = _parse_datetime(time_value)
            if observed_at is None:
                continue
            points.append(
                HourlyWeather(
                    time=observed_at,
                    temperature_c=_series_value(raw, "temperature_2m", index),
                    relative_humidity_pct=_series_value(
                        raw, "relative_humidity_2m", index
                    ),
                    precipitation_mm=_series_value(raw, "precipitation", index),
                    precipitation_probability_pct=_series_value(
                        raw, "precipitation_probability", index
                    ),
                    weather_code=_series_int(raw, "weather_code", index),
                    wind_speed_kmh=_series_value(raw, "wind_speed_10m", index),
                    cloud_cover_pct=_series_value(raw, "cloud_cover", index),
                )
            )
        return points

    @staticmethod
    def _parse_daily(raw: Any) -> list[DailyWeather]:
        if raw is None:
            return []
        if not isinstance(raw, dict):
            raise ValueError("daily weather block must be an object")

        dates = raw.get("time") or []
        if not isinstance(dates, list):
            raise ValueError("daily.time must be a list")

        points: list[DailyWeather] = []
        for index, date_value in enumerate(dates):
            day = _parse_date(date_value)
            if day is None:
                continue
            points.append(
                DailyWeather(
                    date=day,
                    temperature_max_c=_series_value(raw, "temperature_2m_max", index),
                    temperature_min_c=_series_value(raw, "temperature_2m_min", index),
                    precipitation_sum_mm=_series_value(raw, "precipitation_sum", index),
                    weather_code=_series_int(raw, "weather_code", index),
                    wind_speed_max_kmh=_series_value(raw, "wind_speed_10m_max", index),
                    sunrise=_parse_datetime(_series_raw(raw, "sunrise", index)),
                    sunset=_parse_datetime(_series_raw(raw, "sunset", index)),
                )
            )
        return points


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _series_raw(block: dict[str, Any], key: str, index: int) -> Any:
    values = block.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _series_value(block: dict[str, Any], key: str, index: int) -> float | None:
    return _as_optional_float(_series_raw(block, key, index))


def _series_int(block: dict[str, Any], key: str, index: int) -> int | None:
    return _as_optional_int(_series_raw(block, key, index))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])
