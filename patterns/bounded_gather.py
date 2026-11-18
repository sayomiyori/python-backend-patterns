"""Bounded-concurrency helpers for asyncio.

``asyncio.gather`` on a thousand URLs opens a thousand sockets and the
downstream starts rate limiting you. A semaphore keeps the fan-out inside a
budget the dependency agreed to, while preserving result order.

Trade-off: the semaphore is per call, not global. Two endpoints each calling
``map_bounded(limit=10)`` produce 20 concurrent requests. For a shared budget,
hold one semaphore and pass it in.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def bounded_gather(
    awaitables: Iterable[Awaitable[T]],
    limit: int = 10,
    return_exceptions: bool = False,
) -> list[T]:
    """Await everything, at most ``limit`` at a time, keeping input order."""
    if limit <= 0:
        raise ValueError("limit must be positive")

    semaphore = asyncio.Semaphore(limit)

    async def guarded(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable

    tasks = [guarded(awaitable) for awaitable in awaitables]
    results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    return list(results)


async def map_bounded(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    limit: int = 10,
    return_exceptions: bool = False,
) -> list[R]:
    """``bounded_gather`` over a callable and a sequence of arguments."""
    return await bounded_gather(
        (func(item) for item in items),
        limit=limit,
        return_exceptions=return_exceptions,
    )
