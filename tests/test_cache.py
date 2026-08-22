"""Unit tests for the in-memory cache backend."""

import asyncio

import pytest

from app.core.cache import InMemoryCache


@pytest.mark.asyncio
async def test_cache_set_get_and_delete() -> None:
    cache = InMemoryCache(default_ttl_seconds=60)
    await cache.set("weather:noida", {"temp": 32})
    assert await cache.get("weather:noida") == {"temp": 32}

    await cache.delete("weather:noida")
    assert await cache.get("weather:noida") is None


@pytest.mark.asyncio
async def test_cache_ttl_expiry() -> None:
    cache = InMemoryCache(default_ttl_seconds=1)
    await cache.set("key", "value", ttl_seconds=1)
    assert await cache.get("key") == "value"

    await asyncio.sleep(1.05)
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_cache_clear() -> None:
    cache = InMemoryCache()
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None
