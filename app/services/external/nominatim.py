"""OpenStreetMap Nominatim geocoding client."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.cache import CacheBackend, InMemoryCache
from app.core.exceptions import DataUnavailableError, MalformedResponseError
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger
from app.models.location import LocationData

logger = get_logger(__name__)

PROVIDER = "nominatim"


class NominatimClient:
    """Async Nominatim client with caching and polite request pacing.

    Public Nominatim usage policy requires a descriptive User-Agent and asks
    clients to keep request rates to roughly one request per second.
    """

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        base_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str = (
            "IndiaBusinessResearchDecisionAgent/0.1 (contact@example.com)"
        ),
        cache: CacheBackend | None = None,
        cache_ttl_seconds: int = 86400,
        min_request_interval_seconds: float = 1.0,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._cache: CacheBackend = cache or InMemoryCache(
            default_ttl_seconds=cache_ttl_seconds
        )
        self._cache_ttl_seconds = cache_ttl_seconds
        self._min_request_interval_seconds = min_request_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def geocode(self, address: str, *, limit: int = 1) -> LocationData:
        """Resolve an address string to coordinates."""
        query = address.strip()
        if not query:
            raise DataUnavailableError(
                "Address query must not be empty",
                provider=PROVIDER,
            )

        cache_key = f"nominatim:geocode:{query.lower()}:{limit}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Nominatim geocode cache hit for %s", query)
            return LocationData.model_validate(cached)

        payload = await self._request(
            "/search",
            params={
                "q": query,
                "format": "json",
                "addressdetails": 1,
                "limit": limit,
            },
        )
        if not isinstance(payload, list):
            raise MalformedResponseError(
                "Nominatim search response was not a list",
                provider=PROVIDER,
                details=str(payload),
            )
        if not payload:
            raise DataUnavailableError(
                f"No geocoding results for '{query}'",
                provider=PROVIDER,
            )

        location = self._parse_location(payload[0])
        await self._cache.set(
            cache_key,
            location.model_dump(mode="json"),
            ttl_seconds=self._cache_ttl_seconds,
        )
        return location

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> LocationData:
        """Resolve coordinates to a human-readable address."""
        cache_key = f"nominatim:reverse:{latitude:.6f}:{longitude:.6f}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Nominatim reverse cache hit for %s,%s", latitude, longitude)
            return LocationData.model_validate(cached)

        payload = await self._request(
            "/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1,
            },
        )
        if not isinstance(payload, dict):
            raise MalformedResponseError(
                "Nominatim reverse response was not an object",
                provider=PROVIDER,
                details=str(payload),
            )
        if payload.get("error"):
            raise DataUnavailableError(
                str(payload["error"]),
                provider=PROVIDER,
                details=str(payload),
            )

        location = self._parse_location(payload)
        await self._cache.set(
            cache_key,
            location.model_dump(mode="json"),
            ttl_seconds=self._cache_ttl_seconds,
        )
        return location

    async def _request(self, path: str, *, params: dict[str, Any]) -> Any:
        await self._throttle()
        return await self._http.get(
            f"{self._base_url}{path}",
            params=params,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            },
            provider=PROVIDER,
        )

    async def _throttle(self) -> None:
        """Ensure we respect Nominatim's one-request-per-second guidance."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            remaining = self._min_request_interval_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request_at = time.monotonic()

    def _parse_location(self, raw: dict[str, Any]) -> LocationData:
        try:
            latitude = float(raw["lat"])
            longitude = float(raw["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedResponseError(
                "Nominatim response missing valid lat/lon",
                provider=PROVIDER,
                details=str(raw),
            ) from exc

        display_name = raw.get("display_name")
        if not display_name:
            raise DataUnavailableError(
                "Nominatim response did not include a display name",
                provider=PROVIDER,
                details=str(raw),
            )

        address = raw.get("address") or {}
        if not isinstance(address, dict):
            raise MalformedResponseError(
                "Nominatim address block was malformed",
                provider=PROVIDER,
                details=str(raw),
            )

        bounding_box: list[float] | None = None
        if raw.get("boundingbox") is not None:
            try:
                bounding_box = [float(item) for item in raw["boundingbox"]]
            except (TypeError, ValueError) as exc:
                raise MalformedResponseError(
                    "Nominatim bounding box was malformed",
                    provider=PROVIDER,
                    details=str(raw),
                ) from exc

        return LocationData(
            latitude=latitude,
            longitude=longitude,
            display_name=str(display_name),
            place_id=_as_optional_int(raw.get("place_id")),
            osm_type=raw.get("osm_type"),
            osm_id=_as_optional_int(raw.get("osm_id")),
            importance=_as_optional_float(raw.get("importance")),
            address={str(key): str(value) for key, value in address.items()},
            bounding_box=bounding_box,
        )


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
