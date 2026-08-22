"""Overpass API business search using public OpenStreetMap data."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import DataUnavailableError, MalformedResponseError
from app.core.geo import haversine_km
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger
from app.services.external.business_search import (
    BusinessListing,
    BusinessSearchProvider,
)

logger = get_logger(__name__)

PROVIDER = "overpass"

# Map business types to OSM tags (public map features only — no scraping).
_BUSINESS_TAG_QUERIES: dict[str, list[str]] = {
    "cloud kitchen": [
        'node["amenity"="restaurant"]',
        'node["amenity"="fast_food"]',
        'node["amenity"="cafe"]',
        'way["amenity"="restaurant"]',
    ],
    "restaurant": [
        'node["amenity"="restaurant"]',
        'way["amenity"="restaurant"]',
    ],
    "cafe": [
        'node["amenity"="cafe"]',
        'way["amenity"="cafe"]',
    ],
    "grocery": [
        'node["shop"="supermarket"]',
        'node["shop"="convenience"]',
    ],
    "coworking": [
        'node["office"="coworking"]',
        'node["amenity"="coworking_space"]',
    ],
    "retail": [
        'node["shop"]',
        'way["shop"]',
    ],
    "warehouse": [
        'node["building"="warehouse"]',
        'way["building"="warehouse"]',
    ],
}


class OverpassBusinessSearchProvider(BusinessSearchProvider):
    """Search nearby POIs via the public Overpass API (OpenStreetMap)."""

    name = PROVIDER

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        base_url: str = "https://overpass-api.de/api/interpreter",
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")

    async def search_nearby(
        self,
        *,
        business_type: str,
        latitude: float,
        longitude: float,
        radius_km: float = 2.0,
        limit: int = 10,
    ) -> list[BusinessListing]:
        radius_m = max(100, int(radius_km * 1000))
        selectors = _resolve_selectors(business_type)
        query = _build_overpass_query(
            selectors=selectors,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
        )
        logger.info(
            "Overpass search business_type=%s radius_m=%s",
            business_type,
            radius_m,
        )

        payload = await self._http.post(
            self._base_url,
            data={"data": query},
            headers={"Accept": "application/json"},
            provider=PROVIDER,
        )

        elements = payload.get("elements") if isinstance(payload, dict) else None
        if not isinstance(elements, list):
            raise MalformedResponseError(
                "Overpass response missing elements list",
                provider=PROVIDER,
                details=str(payload),
            )
        if not elements:
            raise DataUnavailableError(
                "No nearby businesses found in OpenStreetMap for this query",
                provider=PROVIDER,
            )

        listings: list[BusinessListing] = []
        for element in elements:
            listing = _element_to_listing(
                element,
                origin_lat=latitude,
                origin_lon=longitude,
                business_type=business_type,
            )
            if listing is not None:
                listings.append(listing)

        listings.sort(key=lambda item: item.distance_km or float("inf"))
        return listings[:limit]


def _resolve_selectors(business_type: str) -> list[str]:
    key = business_type.strip().lower().replace("_", " ")
    if key in _BUSINESS_TAG_QUERIES:
        return _BUSINESS_TAG_QUERIES[key]
    # Generic fallback: amenity or shop nodes near the point.
    return [
        'node["amenity"]',
        'node["shop"]',
    ]


def _build_overpass_query(
    *,
    selectors: list[str],
    latitude: float,
    longitude: float,
    radius_m: int,
) -> str:
    around = f"(around:{radius_m},{latitude},{longitude})"
    body_lines = [f"  {selector}{around};" for selector in selectors]
    return (
        "[out:json][timeout:25];\n"
        "(\n" + "\n".join(body_lines) + "\n);\n"
        "out center tags 30;"
    )


def _element_to_listing(
    element: dict[str, Any],
    *,
    origin_lat: float,
    origin_lon: float,
    business_type: str,
) -> BusinessListing | None:
    tags = element.get("tags") or {}
    if not isinstance(tags, dict):
        return None

    name = tags.get("name") or tags.get("brand")
    if not name:
        return None

    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    if lat is None or lon is None:
        return None

    latitude = float(lat)
    longitude = float(lon)
    category = (
        tags.get("amenity") or tags.get("shop") or tags.get("office") or business_type
    )
    address_parts = [
        tags.get(key)
        for key in (
            "addr:housenumber",
            "addr:street",
            "addr:suburb",
            "addr:city",
        )
        if tags.get(key)
    ]
    osm_type = element.get("type", "node")
    osm_id = element.get("id")
    source_url = (
        f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        if osm_id is not None
        else None
    )

    return BusinessListing(
        name=str(name),
        category=str(category) if category else None,
        latitude=latitude,
        longitude=longitude,
        address=", ".join(str(part) for part in address_parts) or None,
        distance_km=round(
            haversine_km(origin_lat, origin_lon, latitude, longitude),
            3,
        ),
        source=PROVIDER,
        source_url=source_url,
        metadata={
            "osm_type": osm_type,
            "osm_id": osm_id,
            "tags": {
                key: value
                for key, value in tags.items()
                if key in {"cuisine", "opening_hours", "phone", "website"}
            },
        },
    )
