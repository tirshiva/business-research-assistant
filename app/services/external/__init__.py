"""External API service clients."""

from app.services.external.nominatim import NominatimClient
from app.services.external.open_meteo import OpenMeteoClient

__all__ = ["NominatimClient", "OpenMeteoClient"]
