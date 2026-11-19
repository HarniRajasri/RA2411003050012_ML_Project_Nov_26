"""Small time helpers. All timestamps are stored as naive UTC and serialised as ISO-8601 with 'Z'."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def epoch(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())
