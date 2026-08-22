"""Reusable async HTTP client built on httpx."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import (
    ExternalTimeoutError,
    HttpRequestError,
    MalformedResponseError,
    RateLimitError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class AsyncHttpClient:
    """Shared async HTTP client that reuses a single connection pool.

    Prefer injecting one instance across services (e.g. via FastAPI lifespan)
    instead of constructing a new client per request.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        default_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers=default_headers or {},
            follow_redirects=True,
        )

    @property
    def raw(self) -> httpx.AsyncClient:
        """Expose the underlying httpx client when advanced control is needed."""
        return self._client

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        provider: str | None = None,
    ) -> Any:
        """Perform a GET request and return parsed JSON."""
        try:
            response = await self._client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("HTTP timeout talking to %s: %s", provider or url, exc)
            raise ExternalTimeoutError(
                f"Request timed out for {provider or url}",
                provider=provider,
                details=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "HTTP transport error talking to %s: %s",
                provider or url,
                exc,
            )
            raise HttpRequestError(
                f"HTTP request failed for {provider or url}",
                provider=provider,
                details=str(exc),
            ) from exc

        return self._parse_response(response, provider=provider)

    async def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        provider: str | None = None,
    ) -> Any:
        """Perform a POST request and return parsed JSON."""
        try:
            response = await self._client.post(
                url,
                data=data,
                json=json,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            logger.warning("HTTP timeout talking to %s: %s", provider or url, exc)
            raise ExternalTimeoutError(
                f"Request timed out for {provider or url}",
                provider=provider,
                details=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "HTTP transport error talking to %s: %s",
                provider or url,
                exc,
            )
            raise HttpRequestError(
                f"HTTP request failed for {provider or url}",
                provider=provider,
                details=str(exc),
            ) from exc

        return self._parse_response(response, provider=provider)

    @staticmethod
    def _parse_response(
        response: httpx.Response,
        *,
        provider: str | None,
    ) -> Any:
        if response.status_code == 429:
            raise RateLimitError(
                f"Rate limited by {provider or 'upstream'}",
                provider=provider,
                status_code=429,
                details=response.text,
            )

        if response.status_code >= 400:
            raise HttpRequestError(
                f"Upstream returned HTTP {response.status_code}",
                provider=provider,
                status_code=response.status_code,
                details=response.text,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise MalformedResponseError(
                f"Malformed JSON response from {provider or 'upstream'}",
                provider=provider,
                status_code=response.status_code,
                details=response.text,
            ) from exc

    async def aclose(self) -> None:
        """Close the underlying client when this wrapper owns it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
