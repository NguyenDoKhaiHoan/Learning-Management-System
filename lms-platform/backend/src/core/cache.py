"""Bounded process-local data cache; callers supply a durable data version."""

import asyncio
from collections import OrderedDict
from copy import deepcopy
from time import monotonic


class ScopedCache:
    def __init__(self, ttl=15, max_entries=256, clock=monotonic):
        self.ttl = ttl
        self.max_entries = max_entries
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    async def get_or_load(self, key, load):
        if self.ttl == 0:
            return await load()
        # Coalesce misses without retaining an unbounded map of per-key locks.
        async with self.lock:
            now = self.clock()
            cached = self.entries.get(key)
            if cached is not None and cached[0] > now:
                self.entries.move_to_end(key)
                self.hits += 1
                return deepcopy(cached[1])
            self.misses += 1
            value = await load()  # Exceptions/cancellation are never cached.
            self.entries[key] = (self.clock() + self.ttl, deepcopy(value))
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)
            return value
