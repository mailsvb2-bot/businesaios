from __future__ import annotations

"""Audit/proof helpers for RuntimeExecutor.

These helpers keep runtime.executor focused on sovereign orchestration while
centralizing proof-event emission in one place.
"""

from typing import Any


def _user_id(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("user_id", "unknown"))
    return "unknown"


def emit_effect_window(event_log: Any, *, opened: bool, decision: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="effect_window_opened" if opened else "effect_window_closed",
        source="runtime_executor",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"action": decision.action},
    )


def emit_decision_executed(event_log: Any, *, decision: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="decision_executed",
        source="runtime_executor",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"action": decision.action},
    )


def emit_reward_observed(event_log: Any, *, decision: Any, reward_engine: Any, reward: float) -> None:
    if event_log is None:
        return
    details = reward_engine.last_details() if hasattr(reward_engine, "last_details") else {}
    event_log.emit(
        event_type="reward_observed",
        source="reward_engine",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"policy_id": decision.policy_id, "reward": float(reward), **(details or {})},
    )


def emit_deployment_proposed(event_log: Any, *, decision: Any, proposal: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="deployment_proposed",
        source="learning_system",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"proposal": proposal},
    )
