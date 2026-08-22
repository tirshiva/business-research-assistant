"""Cache backend protocol used by external service clients."""

from __future__ import annotations

from typing import Any, Protocol


class CacheBackend(Protocol):
    """Abstract cache contract.

    Implementations may be in-memory (MVP) or Redis (future) without changing
    service call sites.
    """

    async def get(self, key: str) -> Any | None:
        """Return a cached value or ``None`` on miss."""

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store ``value`` under ``key`` with an optional TTL."""

    async def delete(self, key: str) -> None:
        """Remove ``key`` from the cache if present."""

    async def clear(self) -> None:
        """Remove all entries from the cache."""
