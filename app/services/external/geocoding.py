"""Geocoding with Nominatim first and Open-Meteo as a fallback."""

from __future__ import annotations

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.models.location import LocationData
from app.services.external.nominatim import NominatimClient
from app.services.external.open_meteo import OpenMeteoClient

logger = get_logger(__name__)


class FallbackGeocoder:
    """Try OSM Nominatim, then Open-Meteo geocoding if Nominatim is blocked."""

    def __init__(
        self,
        nominatim: NominatimClient,
        open_meteo: OpenMeteoClient,
    ) -> None:
        self._nominatim = nominatim
        self._open_meteo = open_meteo

    async def geocode(self, address: str, *, limit: int = 1) -> LocationData:
        try:
            return await self._nominatim.geocode(address, limit=limit)
        except ExternalServiceError as exc:
            logger.warning(
                "Nominatim geocode failed (%s); falling back to Open-Meteo",
                exc.message,
            )
            return await self._open_meteo.geocode(address)

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> LocationData:
        try:
            return await self._nominatim.reverse_geocode(latitude, longitude)
        except ExternalServiceError as exc:
            logger.warning(
                "Nominatim reverse geocode failed (%s); using coordinates only",
                exc.message,
            )
            return LocationData(
                latitude=latitude,
                longitude=longitude,
                display_name=f"{latitude:.5f}, {longitude:.5f}",
                source="coordinates",
            )
