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
    has_append_seq = len(row) >= 10
    offset = 1 if has_append_seq else 0
    payload_index = 8 + offset
    payload = json.loads(row[payload_index]) if row[payload_index] else {}
    event = {
        "event_id": row[offset],
        "tenant_id": row[1 + offset],
        "user_id": row[2 + offset],
        "source": row[3 + offset],
        "event_type": row[4 + offset],
        "timestamp_ms": int(row[5 + offset]),
        "decision_id": row[6 + offset],
        "correlation_id": row[7 + offset],
        "payload": payload,
    }
    if has_append_seq:
        event["append_seq"] = int(row[0])
    return event
