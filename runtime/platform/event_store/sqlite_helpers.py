"""Tiny shared helpers for sqlite event store modules."""

from __future__ import annotations

import json
import time
from typing import Any

MAX_I64 = 2**63 - 1


def _exclusive_end_ms(end_ms: int | None) -> int:
    now = int(time.time() * 1000)
    if end_ms is None:
        return min(now + 1, MAX_I64)
    try:
        e = int(end_ms)
    except Exception:
        return min(now + 1, MAX_I64)
    if e >= MAX_I64:
        return MAX_I64
    return e + 1


def _row_to_event(row) -> dict[str, Any]:
    payload = json.loads(row[8]) if row[8] else {}
    return {
        "event_id": row[0],
        "tenant_id": row[1],
        "user_id": row[2],
        "source": row[3],
        "event_type": row[4],
        "timestamp_ms": int(row[5]),
        "decision_id": row[6],
        "correlation_id": row[7],
        "payload": payload,
    }
