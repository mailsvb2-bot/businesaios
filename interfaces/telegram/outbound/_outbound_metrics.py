"""Pure metrics computation for TelegramOutboundQueue.

Single responsibility: take a list of (priority, wait_ms, exec_ms) samples
and compute a structured snapshot. No I/O, no threading, no side-effects.
"""
from __future__ import annotations



def percentile(values: list[float], p: float) -> float:
    """p-th percentile of values (0..100). Returns 0.0 for empty list."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(int(round((p / 100.0) * (len(s) - 1))), len(s) - 1))
    return float(s[k])


def priority_label(prio: int, *, PRIO_UX=10, PRIO_SYSTEM=20, PRIO_PAYMENTS=30,
                   PRIO_MARKETING=80, PRIO_BULK=85, PRIO_ANALYTICS=90) -> str:
    """Map numeric priority back to a human label."""
    if prio <= PRIO_UX:
        return "ux"
    if prio <= PRIO_SYSTEM:
        return "system"
    if prio <= PRIO_PAYMENTS:
        return "payments"
    if prio >= PRIO_ANALYTICS:
        return "analytics"
    if prio >= PRIO_BULK:
        return "bulk"
    if prio >= PRIO_MARKETING:
        return "marketing"
    return "normal"


def compute_metrics_snapshot(samples: list, qsize: int) -> dict:
    """Build the metrics snapshot dict from raw samples.

    samples: list of (priority: int, wait_ms: float, exec_ms: float)
    """
    buckets: dict[str, list] = {}
    for prio, wait_ms, exec_ms in samples:
        label = priority_label(int(prio))
        buckets.setdefault(label, []).append((float(wait_ms), float(exec_ms)))

    out: dict = {"total_samples": len(samples), "qsize": qsize, "by_priority": {}}
    for label, rows in buckets.items():
        waits = [w for (w, _) in rows]
        execs = [e for (_, e) in rows]
        out["by_priority"][label] = {
            "count": len(rows),
            "wait_ms": {
                "p50": percentile(waits, 50),
                "p95": percentile(waits, 95),
                "p99": percentile(waits, 99),
            },
            "exec_ms": {
                "p50": percentile(execs, 50),
                "p95": percentile(execs, 95),
                "p99": percentile(execs, 99),
            },
        }
    return out
