from __future__ import annotations


def self_heal_payload(
    *,
    reason: str,
    cooldown_ms: int,
    suppressed_until_ms: int,
    qsize: int,
    ux_p95_wait: float,
    dropped: int,
    timestamp_ms: int,
) -> dict:
    return {
        "action": "suppress_marketing",
        "cooldown_ms": int(cooldown_ms),
        "suppressed_until_ms": int(suppressed_until_ms),
        "reason": str(reason),
        "qsize": int(qsize),
        "ux_p95_wait_ms": float(ux_p95_wait),
        "dropped_best_effort_window": int(dropped),
        "timestamp_ms": int(timestamp_ms),
    }
