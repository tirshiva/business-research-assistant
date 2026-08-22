"""Business search provider abstraction for competition research."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class BusinessListing(BaseModel):
    """Normalized competitor / nearby business listing."""

    name: str
    category: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    distance_km: float | None = None
    source: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessSearchProvider(ABC):
    """Pluggable provider for publicly accessible business listings."""

    name: str

    @abstractmethod
    async def search_nearby(
        self,
        *,
        business_type: str,
        latitude: float,
        longitude: float,
        radius_km: float = 2.0,
        limit: int = 10,
    ) -> list[BusinessListing]:
        """Return nearby businesses from a public data source."""
