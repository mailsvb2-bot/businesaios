from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DayWindow:
    day_key: str
    start_ms: int
    end_ms: int


def day_window_utc(day_key: str) -> DayWindow:
    dt = datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=UTC)
    start_ms = int(dt.timestamp() * 1000)
    end_ms = int((dt.timestamp() + 86400) * 1000)
    return DayWindow(day_key=day_key, start_ms=start_ms, end_ms=end_ms)


def day_key_from_ms(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
    return dt.strftime("%Y-%m-%d")


def safe_json(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {}
    return {}


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    i = int(round((len(ys) - 1) * float(q)))
    i = max(0, min(len(ys) - 1, i))
    return float(ys[i])
