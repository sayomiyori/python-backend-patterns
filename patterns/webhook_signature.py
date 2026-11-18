"""Webhook signature verification (Stripe-style ``t=...,v1=...`` header).

Verifying the HMAC proves the body came from someone who knows the secret.
Verifying the timestamp proves the body is fresh — without that check a leaked
payload can be replayed forever, because the signature stays valid.

``hmac.compare_digest`` is used instead of ``==`` so verification time does not
depend on how many leading bytes matched.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable


def compute_signature(secret: bytes | str, body: bytes, timestamp: int) -> str:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    message = str(timestamp).encode("ascii") + b"." + body
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def compute_header(
    secret: bytes | str,
    body: bytes,
    timestamp: int | None = None,
) -> str:
    """Build the header value a sender would put on the request."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    return f"t={ts},v1={compute_signature(secret, body, ts)}"


def parse_header(header: str) -> tuple[int, list[str]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = int(value)
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise ValueError("malformed signature header")
    return timestamp, signatures


def verify_header(
    secret: bytes | str,
    body: bytes,
    header: str,
    tolerance: int = 300,
    now: Callable[[], float] = time.time,
) -> bool:
    """Return True when the signature matches and the timestamp is fresh."""
    try:
        timestamp, signatures = parse_header(header)
    except (ValueError, TypeError):
        return False

    if tolerance >= 0 and abs(now() - timestamp) > tolerance:
        return False

    expected = compute_signature(secret, body, timestamp)
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)
