"""Retry helper with exponential backoff and full jitter.

Third-party calls fail in bursts. Retrying immediately turns a blip into an
outage, so the delay grows exponentially and full jitter spreads retries of
workers that failed at the same moment.

Trade-off: retries make a *transient* error survivable and an *overload* worse.
Only retry idempotent operations, and always keep a hard attempt cap.
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    """Backoff policy. ``attempts`` counts the first try as attempt 1."""

    attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 5.0
    jitter: bool = True

    def delay_for(self, attempt: int) -> float:
        """Delay to sleep after failed ``attempt`` (1-based)."""
        ceiling = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
        return random.uniform(0.0, ceiling) if self.jitter else ceiling


def retry(
    exc_types: tuple[type[BaseException], ...] = (Exception,),
    config: RetryConfig | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a synchronous callable ``config.attempts`` times."""
    cfg = config or RetryConfig()

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(1, cfg.attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exc_types:
                    if attempt == cfg.attempts:
                        raise
                    sleep(cfg.delay_for(attempt))
            raise AssertionError("unreachable")

        return wrapper

    return decorator


def retry_async(
    exc_types: tuple[type[BaseException], ...] = (Exception,),
    config: RetryConfig | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Retry a coroutine function ``config.attempts`` times."""
    cfg = config or RetryConfig()
    sleeper = sleep or asyncio.sleep

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            for attempt in range(1, cfg.attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exc_types:
                    if attempt == cfg.attempts:
                        raise
                    await sleeper(cfg.delay_for(attempt))
            raise AssertionError("unreachable")

        return wrapper

    return decorator
