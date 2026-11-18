"""Keep secrets out of logs, traces and error reports.

Redaction has to happen at the boundary that writes the value out, not at the
call site — somebody will always forget a ``logger.info(payload)``. Two entry
points cover most leaks: ``redact_mapping`` for structured payloads and
``redact_text`` for log lines and tracebacks that already contain a token.

Trade-off: key matching is heuristic. ``{"user": "alice"}`` stays readable,
``{"user_token": "..."}`` does not. When a field is ambiguous, rename it.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

MASK = "***"

DEFAULT_KEY_PATTERN = re.compile(
    r"(?:^|[_\-.])(?:"
    r"pass(?:word|wd)?|secret|token|api[_-]?key|authorization|auth|cookie|"
    r"session(?:[_-]?id)?|credential|cvv|card[_-]?number|private[_-]?key|"
    r"access[_-]?key|client[_-]?secret"
    r")s?(?:$|[_\-.])",
    re.IGNORECASE,
)

_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization: Bearer abc123 / Basic dXNlcjpwYXNz
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/=]{8,}"),
    # Stripe / OpenAI style keys
    re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}"),
    # Telegram bot token: 123456:AA...
    re.compile(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{30,}"),
    # Long hex blobs (session ids, raw hashes presented as secrets)
    re.compile(r"\b[0-9a-f]{32,}\b", re.IGNORECASE),
)


def mask(value: Any) -> str:
    """Mask a scalar, keeping a short prefix for correlation."""
    text = str(value)
    if len(text) <= 8:
        return MASK
    return f"{text[:4]}{MASK}"


def redact_mapping(
    data: Any,
    key_pattern: re.Pattern[str] = DEFAULT_KEY_PATTERN,
    mask_value: str = MASK,
) -> Any:
    """Recursively replace values whose key looks sensitive."""
    if isinstance(data, Mapping):
        cleaned = {}
        for key, value in data.items():
            if isinstance(key, str) and key_pattern.search(key):
                cleaned[key] = mask_value
            else:
                cleaned[key] = redact_mapping(value, key_pattern, mask_value)
        return cleaned
    if isinstance(data, (list, tuple, set)):
        return type(data)(redact_mapping(item, key_pattern, mask_value) for item in data)
    return data


def redact_text(text: str, patterns: Iterable[re.Pattern[str]] = _TEXT_PATTERNS) -> str:
    """Replace token-shaped substrings in free text."""
    result = text
    for pattern in patterns:
        result = pattern.sub(MASK, result)
    return result
