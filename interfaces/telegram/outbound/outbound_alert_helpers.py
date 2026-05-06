from __future__ import annotations

import time
from typing import Any


def build_alert_reason(
    *,
    cond_sla: bool,
    cond_drop: bool,
    cond_q: bool,
    alert_ux_wait_p95_ms: float,
    alert_qsize: int,
) -> str:
    reasons: list[str] = []
    if cond_sla:
        reasons.append(f"SLA_UX_P95_WAIT>{alert_ux_wait_p95_ms:.0f}ms")
    if cond_drop:
        reasons.append("DROPS_BEST_EFFORT")
    if cond_q:
        reasons.append(f"QSIZE>{alert_qsize}")
    return ",".join(reasons) or "ALERT"


def format_bucket_metrics(bucket: dict[str, Any] | None) -> str:
    if not bucket:
        return "p95wait=0 p95exec=0"
    return f"p95wait={bucket['wait_ms']['p95']:.1f}ms p95exec={bucket['exec_ms']['p95']:.1f}ms"


def build_alert_event_payload(
    *,
    reason: str,
    qsize: int,
    executed: int,
    dropped: int,
    rq_glob: int,
    rq_chat: int,
    ux: dict[str, Any] | None,
    mkt: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "reason": str(reason),
        "qsize": int(qsize),
        "executed_window": int(executed),
        "dropped_best_effort_window": int(dropped),
        "requeue_global_window": int(rq_glob),
        "requeue_chat_window": int(rq_chat),
        "ux": ux or {},
        "marketing": mkt or {},
        "timestamp_ms": int(time.time() * 1000),
    }


__all__ = [
    "build_alert_event_payload",
    "build_alert_reason",
    "format_bucket_metrics",
]
