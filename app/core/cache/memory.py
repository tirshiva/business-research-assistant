"""In-memory cache backend suitable for local MVP usage."""

from __future__ import annotations

import time
from typing import Any


class InMemoryCache:
    """Simple process-local cache with optional per-key TTL.

    Not shared across processes or containers. Swap for a Redis-backed
    implementation later by satisfying :class:`CacheBackend`.
    """

    def __init__(self, *, default_ttl_seconds: int = 300) -> None:
        self._default_ttl_seconds = default_ttl_seconds
        self._store: dict[str, tuple[Any, float | None]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if expires_at is not None and time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_at = None if ttl <= 0 else time.monotonic() + ttl
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()
