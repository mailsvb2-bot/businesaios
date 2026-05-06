"""Rolling latency watchdog. In-memory, no background threads."""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from core.observability.perf_watchdog_math import p95 as p95_value
from config.env_flags import env_int
from core.observability.perf_watchdog_state import (
    LAST_EMITTED_OFFENDERS,
    LAST_WATCHDOG_MS,
    RECENT_SLA_BREACHES,
    ROLLING_BTN_TOTALS,
    ROLLING_CK_TO_BTN,
    ROLLING_MAX_SAMPLES,
)
from core.observability.perf_span import sla_budget_ms
from core.observability.silent import swallow


def rolling_track(stage: str, correlation_key: str | None, extra: dict | None, duration_ms: int) -> None:
    """Feed rolling latency tracker. Called by perf.emit_span wrapper."""
    try:
        ck = str(correlation_key or "")
        if not ck:
            return
        if stage == "router":
            if isinstance(extra, dict):
                btn = extra.get("button_key") or extra.get("callback_data") or extra.get("command") or extra.get("text")
                if btn:
                    ROLLING_CK_TO_BTN[ck] = str(btn)[:80]
            return
        if stage != "execute_total":
            return
        btn = ROLLING_CK_TO_BTN.get(ck) or "unknown"
        dq = ROLLING_BTN_TOTALS.get(btn)
        if dq is None:
            from collections import deque
            dq = deque(maxlen=ROLLING_MAX_SAMPLES)
            ROLLING_BTN_TOTALS[btn] = dq
        dq.append(int(max(0, duration_ms)))
        if len(ROLLING_CK_TO_BTN) > 20_000:
            for k in list(ROLLING_CK_TO_BTN.keys())[:5_000]:
                ROLLING_CK_TO_BTN.pop(k, None)
    except Exception:
        return


def recent_sla_breaches(*, limit: int = 3) -> list[dict]:
    """Return recent SLA breaches (in-memory, no I/O)."""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 3
    n = max(0, min(10, n))
    if n <= 0:
        return []
    try:
        return list(RECENT_SLA_BREACHES)[-n:]
    except Exception:
        return []


def rolling_latency_summary(*, top_n: int = 3) -> dict:
    """Small in-memory latency summary for operators."""
    try:
        n = int(top_n)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(10, n))
    budget = sla_budget_ms()
    rows: list[dict[str, int | str]] = []
    for btn, dq in list(ROLLING_BTN_TOTALS.items()):
        xs = list(dq)
        if not xs:
            continue
        rows.append({
            "button": str(btn)[:80],
            "count": int(len(xs)),
            "p95_ms": int(p95_value(xs)),
        })
    rows.sort(key=lambda r: (int(r.get("p95_ms") or 0), int(r.get("count") or 0)), reverse=True)
    return {
        "budget_ms": int(budget),
        "top_buttons": rows[:n],
    }


def watchdog_tick(event_log: Any) -> None:
    """Emit latency SLA offender event periodically."""
    global LAST_WATCHDOG_MS, LAST_EMITTED_OFFENDERS
    try:
        now_ms = int(time.time() * 1000)
        interval_s = env_int("LATENCY_WATCHDOG_INTERVAL_S", 60, lo=10, hi=3600)
        if (now_ms - int(LAST_WATCHDOG_MS or 0)) < interval_s * 1000:
            return
        LAST_WATCHDOG_MS = now_ms

        budget = sla_budget_ms()
        min_samples = env_int("LATENCY_SLA_MIN_SAMPLES", 30, lo=5, hi=10_000)

        offenders: list[dict[str, Any]] = []
        for btn, dq in list(ROLLING_BTN_TOTALS.items()):
            xs = list(dq)
            if len(xs) < min_samples:
                continue
            p95_ms = p95_value(xs)
            if p95_ms >= budget:
                offenders.append({"button": str(btn)[:80], "count": int(len(xs)), "p95_ms": int(p95_ms)})
        offenders.sort(key=lambda r: (int(r.get("p95_ms") or 0), int(r.get("count") or 0)), reverse=True)
        offenders = offenders[:10]

        sig = json.dumps(offenders, sort_keys=True, ensure_ascii=False)
        if sig == (LAST_EMITTED_OFFENDERS or ""):
            return
        LAST_EMITTED_OFFENDERS = sig

        if event_log is None or not hasattr(event_log, "emit"):
            return

        try:
            RECENT_SLA_BREACHES.append({
                "ts_ms": int(now_ms),
                "budget_ms": int(budget),
                "offenders": offenders,
            })
        except Exception:
            swallow(__name__, "core/observability/perf_watchdog")

        event_log.emit(
            event_type="latency_sla_breached",
            source="perf.watchdog",
            user_id="system",
            decision_id=None,
            correlation_id=None,
            payload={"budget_ms": int(budget), "offenders": offenders, "ts_ms": int(now_ms)},
        )
    except Exception:
        return


__all__ = ["rolling_track", "recent_sla_breaches", "rolling_latency_summary", "watchdog_tick"]
