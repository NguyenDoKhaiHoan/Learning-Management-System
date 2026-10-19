"""Cache values cannot leak mutations, outlive TTL or grow without bounds."""

import asyncio

import pytest

from src.core.cache import ScopedCache


async def test_cache_copy_expiry_lru_and_disabled():
    now = [0]
    cache = ScopedCache(ttl=10, max_entries=2, clock=lambda: now[0])
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        return {"items": [calls]}

    first = await cache.get_or_load("a", load)
    first["items"].append("private mutation")
    assert (await cache.get_or_load("a", load))["items"] == [1]
    await cache.get_or_load("b", load)
    await cache.get_or_load("c", load)
    assert len(cache.entries) == 2 and "a" not in cache.entries
    now[0] = 11
    assert (await cache.get_or_load("c", load))["items"] == [4]
    disabled = ScopedCache(ttl=0)
    await disabled.get_or_load("a", load)
    await disabled.get_or_load("a", load)
    assert len(disabled.entries) == 0 and calls == 6


async def test_cache_coalesces_misses_and_does_not_cache_failure_or_cancellation():
    cache = ScopedCache()
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        started.set()
        await finish.wait()
        return {"value": calls}

    first = asyncio.create_task(cache.get_or_load("cancelled", load))
    await started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert not cache.entries
    finish.set()
    results = await asyncio.gather(*(cache.get_or_load("same", load) for _ in range(5)))
    assert calls == 2 and all(result == {"value": 2} for result in results)

    async def fail():
        raise RuntimeError("loader unavailable")

    with pytest.raises(RuntimeError):
        await cache.get_or_load("failed", fail)
    assert "failed" not in cache.entries
