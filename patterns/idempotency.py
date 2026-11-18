"""Idempotency keys for webhook and payment handlers.

The contract: the same ``Idempotency-Key`` executed twice must produce one side
effect and return the first result. Duplicate deliveries are the norm, not the
exception — payment providers retry, message brokers redeliver, clients time out
after the server already committed.

Trade-off: an in-memory store only protects a single process and loses state on
restart. Swap ``InMemoryIdempotencyStore`` for a Redis/Postgres implementation
of the same three methods (``begin`` / ``finish`` / ``release``) for real use;
``run_once`` stays unchanged.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


class IdempotencyConflict(RuntimeError):
    """A request with this key is already being processed."""


@dataclass
class Entry:
    value: Any = None
    expires_at: float = 0.0
    in_flight: bool = True


@dataclass
class InMemoryIdempotencyStore:
    clock: Callable[[], float] = time.monotonic
    _entries: dict[str, Entry] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def _live(self, key: str) -> Entry | None:
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at <= self.clock():
            del self._entries[key]
            return None
        return entry

    def begin(self, key: str, ttl: float) -> bool:
        """Claim ``key``. Returns False when it already exists."""
        with self._lock:
            if self._live(key) is not None:
                return False
            self._entries[key] = Entry(expires_at=self.clock() + ttl)
            return True

    def finish(self, key: str, value: Any) -> None:
        with self._lock:
            entry = self._live(key)
            if entry is None:
                return
            entry.value = value
            entry.in_flight = False

    def release(self, key: str) -> None:
        """Drop a claim so the request can be retried after a crash."""
        with self._lock:
            self._entries.pop(key, None)

    def get(self, key: str) -> Entry | None:
        with self._lock:
            entry = self._live(key)
            if entry is None or entry.in_flight:
                return None
            return entry

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


def run_once(
    store: InMemoryIdempotencyStore,
    key: str,
    fn: Callable[[], Any],
    ttl: float = 3600.0,
) -> tuple[Any, bool]:
    """Run ``fn`` at most once per ``key``.

    Returns ``(value, replayed)``. ``replayed`` is True when the stored result
    was returned instead of executing the side effect again. Raises
    ``IdempotencyConflict`` when another worker is mid-flight on the same key.
    """
    cached = store.get(key)
    if cached is not None:
        return cached.value, True

    if not store.begin(key, ttl):
        raise IdempotencyConflict(key)

    try:
        value = fn()
    except BaseException:
        store.release(key)
        raise

    store.finish(key, value)
    return value, False
