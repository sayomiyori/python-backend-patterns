"""Transactional outbox.

Writing to the database and publishing to a broker are two systems, and one of
them will fail. The outbox pattern makes the database commit the single source
of truth: the event is stored in the same transaction as the state change, then
a relay publishes pending rows and marks them done.

Delivery is at-least-once. Consumers must deduplicate — pair this with
``patterns.idempotency`` on the receiving side.

Trade-off: ``drain`` is a polling relay. For production, run it from a worker
(cron or Celery beat) with a lease/lock so two relays do not publish the same
row, and add an ``attempts`` based dead-letter policy.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class OutboxRecord:
    id: str
    topic: str
    payload: dict[str, Any]
    created_at: float
    published_at: float | None = None
    attempts: int = 0


@dataclass
class InMemoryOutbox:
    clock: Callable[[], float] = time.monotonic
    _records: dict[str, OutboxRecord] = field(default_factory=dict, init=False)
    _order: list[str] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def add(self, topic: str, payload: dict[str, Any]) -> OutboxRecord:
        record = OutboxRecord(
            id=uuid.uuid4().hex,
            topic=topic,
            payload=payload,
            created_at=self.clock(),
        )
        with self._lock:
            self._records[record.id] = record
            self._order.append(record.id)
        return record

    def pending(self, limit: int = 100) -> list[OutboxRecord]:
        with self._lock:
            result = []
            for record_id in self._order:
                record = self._records[record_id]
                if record.published_at is None:
                    result.append(record)
                    if len(result) >= limit:
                        break
            return result

    def mark_published(self, record_id: str) -> None:
        with self._lock:
            record = self._records.get(record_id)
            if record is not None:
                record.published_at = self.clock()
                record.attempts += 1

    def mark_failed(self, record_id: str) -> None:
        with self._lock:
            record = self._records.get(record_id)
            if record is not None:
                record.attempts += 1

    def drain(
        self,
        publish: Callable[[OutboxRecord], None],
        limit: int = 100,
    ) -> tuple[int, int]:
        """Publish pending records. Returns ``(published, failed)``."""
        published = failed = 0
        for record in self.pending(limit):
            try:
                publish(record)
            except Exception:
                self.mark_failed(record.id)
                failed += 1
            else:
                self.mark_published(record.id)
                published += 1
        return published, failed

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
