from __future__ import annotations

from datetime import UTC, datetime, timezone
from uuid import uuid4


def _utc_timestamp_token() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")


def new_lesson_id() -> str:
    return f"lesson-{_utc_timestamp_token()}-{uuid4().hex[:8]}"


def new_pattern_id() -> str:
    return f"pattern-{_utc_timestamp_token()}-{uuid4().hex[:8]}"


def new_memory_link_id() -> str:
    return f"mlink-{_utc_timestamp_token()}-{uuid4().hex[:8]}"
