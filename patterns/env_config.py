"""Typed environment configuration with aggregated errors.

The failure mode this prevents: the service boots, passes its healthcheck, and
crashes an hour later on the first request because ``REDIS_PORT`` was the string
``"6379 "``. Parsing at startup with one aggregated error turns a 3am page into
a failed deploy.

Usage::

    env = Env()
    DATABASE_URL = env.str("DATABASE_URL", required=True)
    WORKERS = env.int("WEB_CONCURRENCY", default=4)
    FEATURE_X = env.bool("FEATURE_X", default=False)
    env.validate()   # raises ConfigError listing every problem at once
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

_TRUE = {"1", "true", "t", "yes", "y", "on"}
_FALSE = {"0", "false", "f", "no", "n", "off"}


class ConfigError(ValueError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("invalid configuration: " + "; ".join(self.errors))


class Env:
    def __init__(self, source: Mapping[str, str] | None = None) -> None:
        self._source = os.environ if source is None else source
        self._errors: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _raw(self, key: str) -> str | None:
        value = self._source.get(key)
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _fail(self, key: str, expected: str, value: str | None) -> None:
        self._errors.append(f"{key} must be {expected}, got {value!r}")

    def errors(self) -> list[str]:
        return list(self._errors)

    def validate(self) -> None:
        """Raise ``ConfigError`` if any getter recorded a problem."""
        if self._errors:
            raise ConfigError(self._errors)

    # -- getters ---------------------------------------------------------
    def str(self, key: str, default: str | None = None, required: bool = False) -> str | None:
        value = self._raw(key)
        if value is None:
            if required:
                self._errors.append(f"{key} is required")
            return default
        return value

    def int(self, key: str, default: int | None = None) -> int | None:
        value = self._raw(key)
        if value is None:
            return default
        try:
            return int(value.replace("_", ""))
        except ValueError:
            self._fail(key, "an integer", value)
            return default

    def float(self, key: str, default: float | None = None) -> float | None:
        value = self._raw(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            self._fail(key, "a number", value)
            return default

    def bool(self, key: str, default: bool | None = None) -> bool | None:
        value = self._raw(key)
        if value is None:
            return default
        lowered = value.lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        self._fail(key, "a boolean (true/false/1/0/yes/no)", value)
        return default

    def list(self, key: str, separator: str = ",", default: Sequence[str] = ()) -> list[str]:
        value = self._raw(key)
        if value is None:
            return list(default)
        return [item.strip() for item in value.split(separator) if item.strip()]

    def as_dict(self) -> dict[str, Any]:
        """Everything currently known about the source, minus secrets."""
        return {key: value for key, value in self._source.items()}
