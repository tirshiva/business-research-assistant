"""Application-level location / geocoding models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LocationData(BaseModel):
    """Normalized geocoding result returned by the Nominatim client."""

    latitude: float
    longitude: float
    display_name: str
    place_id: int | None = None
    osm_type: str | None = None
    osm_id: int | None = None
    importance: float | None = None
    address: dict[str, str] = Field(default_factory=dict)
    bounding_box: list[float] | None = None
    source: str = "nominatim"
