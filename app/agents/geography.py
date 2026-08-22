"""Geography research agent powered by Nominatim / OpenStreetMap."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, model_validator

from app.agents.base import ResearchAgent
from app.agents.schemas import AgentFinding, AgentResult, AgentSource
from app.core.exceptions import DataUnavailableError, ExternalServiceError
from app.core.geo import haversine_km
from app.models.location import LocationData
from app.services.external.nominatim import NominatimClient


class GeographyAgentInput(BaseModel):
    """Input schema for the geography agent."""

    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Optional reference point for distance reporting.
    reference_latitude: float | None = None
    reference_longitude: float | None = None

    @model_validator(mode="after")
    def require_location_or_coordinates(self) -> GeographyAgentInput:
        has_location = bool(self.location and self.location.strip())
        has_coords = self.latitude is not None and self.longitude is not None
        if not has_location and not has_coords:
            raise ValueError("Provide location and/or latitude+longitude")
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class GeographyAgent(ResearchAgent):
    """Resolve places and surrounding geographic context via Nominatim."""

    name: ClassVar[str] = "geography"
    allowed_tools: ClassVar[list[str]] = [
        "nominatim.geocode",
        "nominatim.reverse_geocode",
    ]

    def __init__(self, nominatim: NominatimClient) -> None:
        self._nominatim = nominatim

    async def run(self, payload: GeographyAgentInput) -> AgentResult:
        self._log_start(payload)
        sources: list[AgentSource] = []
        findings: list[AgentFinding] = []
        errors: list[str] = []

        try:
            place = await self._resolve_place(payload)
        except DataUnavailableError as exc:
            return AgentResult(
                agent="geography",
                findings=[],
                sources=[],
                confidence=0.0,
                status="data_unavailable",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )
        except ExternalServiceError as exc:
            return AgentResult(
                agent="geography",
                findings=[],
                sources=[],
                confidence=0.0,
                status="failed",
                errors=[exc.message],
                allowed_tools=list(self.allowed_tools),
            )

        sources.append(
            AgentSource(
                name=(
                    "Open-Meteo Geocoding"
                    if place.source == "open-meteo"
                    else "OpenStreetMap Nominatim"
                ),
                url=(
                    "https://open-meteo.com/en/docs/geocoding-api"
                    if place.source == "open-meteo"
                    else "https://nominatim.openstreetmap.org/"
                ),
                tool="nominatim" if place.source == "nominatim" else place.source,
            )
        )

        distance_km = None
        if (
            payload.reference_latitude is not None
            and payload.reference_longitude is not None
        ):
            distance_km = round(
                haversine_km(
                    payload.reference_latitude,
                    payload.reference_longitude,
                    place.latitude,
                    place.longitude,
                ),
                3,
            )

        bbox = place.bounding_box
        surrounding = {
            "address_components": place.address,
            "bounding_box": bbox,
            "importance": place.importance,
            "osm_type": place.osm_type,
            "osm_id": place.osm_id,
        }

        findings.append(
            AgentFinding(
                title="Resolved location",
                summary=place.display_name,
                data={
                    "coordinates": {
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                    },
                    "address": place.display_name,
                    "surrounding": surrounding,
                    "distance_km_from_reference": distance_km,
                },
                confidence=(
                    0.9
                    if place.importance is None
                    else min(0.95, 0.6 + place.importance)
                ),
            )
        )

        # Nearby administrative context from address parts when available.
        admin_bits = {
            key: value
            for key, value in place.address.items()
            if key
            in {
                "suburb",
                "neighbourhood",
                "city",
                "town",
                "state",
                "county",
                "postcode",
                "country",
            }
        }
        if admin_bits:
            findings.append(
                AgentFinding(
                    title="Surrounding geographic context",
                    summary="Administrative / place hierarchy from Nominatim.",
                    data=admin_bits,
                    confidence=0.8,
                )
            )

        if bbox and len(bbox) == 4:
            # Nominatim bbox: [south_lat, north_lat, west_lon, east_lon]
            south, north, west, east = (float(v) for v in bbox)
            span_ns_km = haversine_km(south, west, north, west)
            span_ew_km = haversine_km(south, west, south, east)
            findings.append(
                AgentFinding(
                    title="Bounding-box span",
                    summary=(
                        f"Approx. N–S span {span_ns_km:.2f} km, "
                        f"E–W span {span_ew_km:.2f} km."
                    ),
                    data={
                        "span_north_south_km": round(span_ns_km, 3),
                        "span_east_west_km": round(span_ew_km, 3),
                        "bounding_box": bbox,
                    },
                    confidence=0.75,
                )
            )

        return AgentResult(
            agent="geography",
            findings=findings,
            sources=sources,
            confidence=0.88 if findings else 0.0,
            status="completed" if findings else "data_unavailable",
            errors=errors,
            allowed_tools=list(self.allowed_tools),
        )

    async def _resolve_place(self, payload: GeographyAgentInput) -> LocationData:
        if payload.location and payload.location.strip():
            return await self._nominatim.geocode(payload.location.strip())
        assert payload.latitude is not None and payload.longitude is not None
        return await self._nominatim.reverse_geocode(
            payload.latitude,
            payload.longitude,
        )
