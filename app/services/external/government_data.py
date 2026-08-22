"""India government open-data provider abstraction and data.gov.in client."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import (
    DataUnavailableError,
    HttpRequestError,
    MalformedResponseError,
)
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger

logger = get_logger(__name__)


class GovernmentDatasetMetadata(BaseModel):
    """Metadata for a discoverable government open-data dataset."""

    id: str
    title: str
    notes: str | None = None
    organization: str | None = None
    source_url: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class GovernmentDataProvider(ABC):
    """Abstraction over India government open-data catalogs."""

    name: str

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[GovernmentDatasetMetadata]:
        """Search catalog metadata for datasets matching ``query``."""

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> GovernmentDatasetMetadata:
        """Retrieve metadata for a single dataset."""


class DataGovInProvider(GovernmentDataProvider):
    """CKAN-compatible client for data.gov.in catalog metadata.

    Uses the public ``package_search`` / ``package_show`` action API for
    discovery. Does not fabricate datasets. When the API is unreachable or
    returns no matches, raises :class:`DataUnavailableError`.
    """

    name = "data.gov.in"

    def __init__(
        self,
        http_client: AsyncHttpClient,
        *,
        base_url: str = "https://data.gov.in/api/3/action",
        api_key: str | None = None,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = (api_key or "").strip() or None

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[GovernmentDatasetMetadata]:
        q = query.strip()
        if not q:
            raise DataUnavailableError(
                "Government data search query must not be empty",
                provider=self.name,
            )

        params: dict[str, Any] = {"q": q, "rows": limit}
        if self._api_key:
            params["api-key"] = self._api_key

        logger.info("Searching data.gov.in catalog q=%r limit=%s", q, limit)
        try:
            payload = await self._http.get(
                f"{self._base_url}/package_search",
                params=params,
                provider=self.name,
            )
        except HttpRequestError as exc:
            if exc.status_code in {401, 403}:
                raise DataUnavailableError(
                    "data.gov.in catalog requires authentication or is forbidden",
                    provider=self.name,
                    status_code=exc.status_code,
                    details=exc.details,
                ) from exc
            raise DataUnavailableError(
                "data.gov.in catalog search is unavailable",
                provider=self.name,
                status_code=exc.status_code,
                details=exc.details,
            ) from exc

        results = _extract_search_results(payload)
        if not results:
            raise DataUnavailableError(
                f"No data.gov.in datasets found for query '{q}'",
                provider=self.name,
            )
        return [_map_package(item) for item in results]

    async def get_dataset(self, dataset_id: str) -> GovernmentDatasetMetadata:
        package_id = dataset_id.strip()
        if not package_id:
            raise DataUnavailableError(
                "dataset_id must not be empty",
                provider=self.name,
            )

        params: dict[str, Any] = {"id": package_id}
        if self._api_key:
            params["api-key"] = self._api_key

        try:
            payload = await self._http.get(
                f"{self._base_url}/package_show",
                params=params,
                provider=self.name,
            )
        except HttpRequestError as exc:
            raise DataUnavailableError(
                f"data.gov.in dataset '{package_id}' is unavailable",
                provider=self.name,
                status_code=exc.status_code,
                details=exc.details,
            ) from exc

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise MalformedResponseError(
                "data.gov.in package_show returned an unexpected payload",
                provider=self.name,
                details=str(payload),
            )
        return _map_package(result)


def _extract_search_results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise MalformedResponseError(
            "data.gov.in search response was not an object",
            provider="data.gov.in",
            details=str(payload),
        )
    if payload.get("success") is False:
        raise DataUnavailableError(
            str(payload.get("error") or "data.gov.in reported failure"),
            provider="data.gov.in",
            details=str(payload),
        )
    result = payload.get("result") or {}
    results = result.get("results") if isinstance(result, dict) else None
    if results is None:
        raise MalformedResponseError(
            "data.gov.in search response missing result.results",
            provider="data.gov.in",
            details=str(payload),
        )
    if not isinstance(results, list):
        raise MalformedResponseError(
            "data.gov.in search results were not a list",
            provider="data.gov.in",
            details=str(payload),
        )
    return [item for item in results if isinstance(item, dict)]


def _map_package(item: dict[str, Any]) -> GovernmentDatasetMetadata:
    org = item.get("organization") or {}
    org_name = None
    if isinstance(org, dict):
        org_name = org.get("title") or org.get("name")

    resources_raw = item.get("resources") or []
    resources: list[dict[str, Any]] = []
    if isinstance(resources_raw, list):
        for resource in resources_raw:
            if not isinstance(resource, dict):
                continue
            resources.append(
                {
                    "id": resource.get("id"),
                    "name": resource.get("name"),
                    "format": resource.get("format"),
                    "url": resource.get("url"),
                }
            )

    tags_raw = item.get("tags") or []
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for tag in tags_raw:
            if isinstance(tag, dict) and tag.get("name"):
                tags.append(str(tag["name"]))
            elif isinstance(tag, str):
                tags.append(tag)

    package_id = str(item.get("id") or item.get("name") or "")
    title = str(item.get("title") or item.get("name") or package_id)
    return GovernmentDatasetMetadata(
        id=package_id,
        title=title,
        notes=item.get("notes"),
        organization=str(org_name) if org_name else None,
        source_url=(
            f"https://data.gov.in/dataset/{item.get('name')}"
            if item.get("name")
            else None
        ),
        resources=resources,
        tags=tags,
    )
