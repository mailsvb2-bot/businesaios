from __future__ import annotations

import secrets
import time


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str = "id") -> str:
    """Short stable id (good enough for correlation within one system)."""

    return f"{prefix}_{secrets.token_hex(8)}"


def new_request_id(prefix: str = "llm") -> str:
    # backward-compatible alias
    return new_id(prefix)


def day_key_utc(ts_ms: int | None = None) -> str:
    if ts_ms is None:
        ts_ms = now_ms()
    t = time.gmtime(ts_ms / 1000.0)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
