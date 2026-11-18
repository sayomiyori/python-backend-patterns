"""JSON logs that a log aggregator can actually index.

Plain-text logs are fine until something breaks at 3am and you need every line
from one request. A JSON formatter plus a request-id context variable gives you
grep-by-id without touching call sites.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


def new_request_id() -> str:
    """Start a fresh request id for the current context."""
    value = uuid.uuid4().hex[:12]
    request_id.set(value)
    return value


class JsonFormatter(logging.Formatter):
    """Render a ``LogRecord`` as one JSON object per line."""

    def __init__(
        self,
        service: str = "app",
        redact: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.redact = redact

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
        }

        current = request_id.get()
        if current:
            payload["request_id"] = current

        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        if self.redact is not None:
            payload = self.redact(payload)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure(
    level: int = logging.INFO,
    service: str = "app",
    stream=None,
    redact: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> logging.Logger:
    """Attach a JSON handler to the root logger exactly once."""
    logger = logging.getLogger()
    for handler in logger.handlers:
        if getattr(handler, "_json_backend_patterns", False):
            return logger

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter(service=service, redact=redact))
    handler._json_backend_patterns = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
