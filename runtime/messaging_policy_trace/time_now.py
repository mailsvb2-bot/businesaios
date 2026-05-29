from __future__ import annotations

from datetime import datetime, timezone, UTC


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
