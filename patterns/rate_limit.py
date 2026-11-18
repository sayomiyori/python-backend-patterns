"""Token bucket rate limiter.

``capacity`` is the burst size, ``refill_per_second`` the sustained rate. The
bucket is a plain in-process object, so limits are per worker — for a global
limit use Redis (``INCR`` + ``EXPIRE`` or a Lua script) and keep this as the
local fast path.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    clock: Callable[[], float] = time.monotonic
    _tokens: float = field(default=0.0, init=False)
    _updated: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if self.refill_per_second < 0:
            raise ValueError("refill_per_second must not be negative")
        self._tokens = float(self.capacity)
        self._updated = self.clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self._updated)
        self._tokens = min(
            float(self.capacity), self._tokens + elapsed * self.refill_per_second
        )
        self._updated = now

    @property
    def tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Take ``tokens`` if available. Never blocks."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire(
        self,
        tokens: float = 1.0,
        timeout: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 0.01,
    ) -> bool:
        """Block until ``tokens`` are available or ``timeout`` expires."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if self.try_acquire(tokens):
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            sleep(poll_interval)
