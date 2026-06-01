from __future__ import annotations

from typing import Any, Dict


def build_world_model_pinned_event(
    *,
    decision_id: str,
    user_id: str,
    world_model_meta: dict[str, Any] | None,
    issuer_id: str,
    timestamp_ms: int,
) -> dict[str, Any]:
    return {
        "type": "decision.world_model_pinned",
        "decision_id": str(decision_id),
        "user_id": str(user_id),
        "issuer_id": str(issuer_id),
        "timestamp_ms": int(timestamp_ms),
        "world_model_meta": dict(world_model_meta or {}),
    }


def build_world_model_pin_check_event(
    *,
    decision_id: str,
    user_id: str,
    check_result: dict[str, Any],
    issuer_id: str,
    timestamp_ms: int,
) -> dict[str, Any]:
    return {
        "type": "decision.world_model_pin_checked",
        "decision_id": str(decision_id),
        "user_id": str(user_id),
        "issuer_id": str(issuer_id),
        "timestamp_ms": int(timestamp_ms),
        "pin_check": dict(check_result),
    }
