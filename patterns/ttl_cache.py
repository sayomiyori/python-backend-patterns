"""In-process TTL + LRU cache.

Two expiration rules at once: entries die after ``ttl`` seconds, and the oldest
entry is evicted when ``maxsize`` is exceeded. Without the size bound a cache on
user-controlled keys is a memory leak with extra steps.

Not a distributed cache. If two replicas must agree, use Redis.
"""

from __future__ import annotations

import functools
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class TTLCache:
    def __init__(
        self,
        maxsize: int = 128,
        ttl: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.maxsize = maxsize
        self.ttl = ttl
        self._clock = clock
        self._data: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def _drop_expired(self) -> None:
        now = self._clock()
        stale = [key for key, (expires, _) in self._data.items() if expires <= now]
        for key in stale:
            del self._data[key]

    def get(self, key: Hashable, default: Any = None) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            expires_at, value = entry
            if expires_at <= self._clock():
                del self._data[key]
                return default
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._drop_expired()
            self._data.pop(key, None)
            self._data[key] = (self._clock() + self.ttl, value)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            self._drop_expired()
            return len(self._data)

    def __contains__(self, key: Hashable) -> bool:
        return self.get(key, _MISSING) is not _MISSING


_MISSING = object()


def ttl_cache(
    maxsize: int = 128,
    ttl: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Memoise a pure function with expiration and a size bound.

    Arguments must be hashable; a list or dict argument raises ``TypeError`` on
    the first call rather than silently missing the cache every time.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        cache = TTLCache(maxsize=maxsize, ttl=ttl, clock=clock)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            hit = cache.get(key, _MISSING)
            if hit is not _MISSING:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value)
            return value

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
