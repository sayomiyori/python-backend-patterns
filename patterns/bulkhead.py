"""Bulkhead: cap concurrent calls to one dependency.

A thread pool shared between a slow PDF renderer and the payment client means a
renderer backlog starves payments. A bulkhead gives each dependency its own
bounded concurrency, so saturation in one stays there.

Difference from a rate limiter: a rate limiter controls calls *per second*, a
bulkhead controls calls *in flight*. You usually want both.
"""

from __future__ import annotations

import threading
from types import TracebackType


class BulkheadFull(RuntimeError):
    """Raised when the bulkhead is saturated and the caller did not wait."""


class Bulkhead:
    def __init__(self, name: str, limit: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        self.name = name
        self.limit = limit
        self._semaphore = threading.BoundedSemaphore(limit)
        self._lock = threading.Lock()
        self._active = 0
        self._rejected = 0
        self._completed = 0

    def acquire(self, timeout: float | None = None) -> bool:
        """Take a slot. ``timeout=None`` waits forever, ``0`` never waits."""
        acquired = self._semaphore.acquire(blocking=True, timeout=timeout)
        with self._lock:
            if acquired:
                self._active += 1
            else:
                self._rejected += 1
        return acquired

    def release(self) -> None:
        with self._lock:
            if self._active > 0:
                self._active -= 1
                self._completed += 1
        self._semaphore.release()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "limit": self.limit,
                "active": self._active,
                "completed": self._completed,
                "rejected": self._rejected,
            }

    def __enter__(self) -> "Bulkhead":
        """Enter without waiting. A saturated bulkhead fails fast so the caller
        can shed load or return 503 instead of piling up threads."""
        if not self.acquire(timeout=0):
            raise BulkheadFull(f"bulkhead {self.name!r} is full")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
