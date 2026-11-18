"""Cursor pagination that survives concurrent inserts.

``OFFSET 10000 LIMIT 50`` gets slower the deeper you go and silently skips rows
when someone inserts in front of the cursor. Keyset pagination fixes both: the
cursor carries the last seen sort key, and the next query is a range scan.

The token is base64url(JSON) so it is opaque to clients but debuggable for you.
It is *not* signed: a client can forge a cursor, which is fine because the
cursor only encodes a position, never a permission.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence, TypeVar

T = TypeVar("T")


def encode_cursor(values: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(values), separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> dict[str, Any]:
    if not token:
        raise ValueError("empty cursor")
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid cursor")
    return data


@dataclass
class Page:
    items: list[Any]
    next_cursor: str | None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


def paginate(
    items: Sequence[T],
    key: Callable[[T], Any],
    limit: int,
    after: str | None = None,
) -> Page:
    """Return one page of ``items`` ordered by ``key``.

    ``key`` must return a JSON-serialisable value with a total order (int,
    float, str, ISO-8601 timestamp). The comparison is done on the sorted
    sequence, so callers can pass a lazy list from the database already.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")

    ordered = sorted(items, key=key)
    start = 0
    if after:
        boundary = decode_cursor(after).get("k")
        if boundary is not None:
            for index, item in enumerate(ordered):
                if key(item) > boundary:
                    start = index
                    break
            else:
                start = len(ordered)

    window = ordered[start : start + limit]
    has_more = start + limit < len(ordered)
    next_cursor = encode_cursor({"k": key(window[-1])}) if has_more and window else None
    return Page(items=list(window), next_cursor=next_cursor)
