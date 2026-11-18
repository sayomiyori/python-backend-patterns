"""Minimal thread-safe circuit breaker.

States:

    CLOSED     calls pass through, failures are counted
    OPEN       calls fail fast, nothing touches the upstream
    HALF_OPEN  one probe is allowed after ``recovery_timeout``

A healthy probe closes the circuit; a failed probe re-opens it for another
recovery window.

Trade-off: this is the single-process variant. With N replicas each one keeps
its own state, so the upstream sees up to N probes per window. That is fine for
"shed load during an outage" and wrong for "enforce a global budget".
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar

T = TypeVar("T")


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised instead of calling an upstream the breaker considers broken."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    clock: Callable[[], float] = time.monotonic
    _state: State = field(default=State.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    @property
    def state(self) -> State:
        with self._lock:
            return self._refresh()

    def _refresh(self) -> State:
        if (
            self._state is State.OPEN
            and self.clock() - self._opened_at >= self.recovery_timeout
        ):
            self._state = State.HALF_OPEN
        return self._state

    def allows(self) -> bool:
        return self.state is not State.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = State.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state is State.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = State.OPEN
                self._opened_at = self.clock()

    def reset(self) -> None:
        with self._lock:
            self._state = State.CLOSED
            self._failures = 0
            self._opened_at = 0.0

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        if not self.allows():
            raise CircuitOpenError("circuit is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
