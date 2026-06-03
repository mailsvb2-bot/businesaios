from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from execution.closed_loop_support import (
    build_approval_handoff as _build_approval_handoff_owner,
    build_recovery_summary as _build_recovery_summary_owner,
    normalize_approval_context as _normalize_approval_context_owner,
)
from execution.closed_loop_economic_state import (
    apply_economic_history_to_state as _apply_economic_history_to_state_owner,
    economic_event_id as _economic_event_id_owner,
    safe_dict as _safe_dict_owner,
    safe_int as _safe_int_owner,
    stable_reliability_trace as _stable_reliability_trace_owner,
)

CANON_CLOSED_LOOP_ORCHESTRATOR_SUPPORT = True

def _safe_dict(value: object) -> dict[str, Any]:
    return _safe_dict_owner(value)


def _safe_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _safe_int(value: object) -> int | None:
    return _safe_int_owner(value)


def _stable_reliability_trace(*, action: Mapping[str, Any], verification: Mapping[str, Any], execution_receipt: Mapping[str, Any]) -> dict[str, Any]:
    return _stable_reliability_trace_owner(action=action, verification=verification, execution_receipt=execution_receipt)


def _economic_event_id(*, action: Mapping[str, Any], persisted_payload: Mapping[str, Any], reliability_trace: Mapping[str, Any]) -> str:
    return _economic_event_id_owner(action=action, persisted_payload=persisted_payload, reliability_trace=reliability_trace)


def _apply_economic_history_to_state(*, world_state: Any, economic_feedback: Mapping[str, Any], roi_history: Mapping[str, Any], policy_snapshot: Mapping[str, Any]) -> Any:
    return _apply_economic_history_to_state_owner(
        world_state=world_state,
        economic_feedback=economic_feedback,
        roi_history=roi_history,
        policy_snapshot=policy_snapshot,
    )



def _extract_inference_runtime_context(*, action: Mapping[str, Any], execution_receipt: Mapping[str, Any]) -> dict[str, Any]:
    for source in (execution_receipt, action):
        source_payload = _safe_dict(source)
        provider_name = str(source_payload.get('inference_provider_name') or '').strip()
        capacity_tier = str(source_payload.get('inference_capacity_tier') or '').strip()
        if not provider_name and not capacity_tier:
            continue
        return {
            'provider_name': provider_name or None,
            'capacity_tier': capacity_tier or None,
            'estimated_cost_usd': source_payload.get('inference_estimated_cost_usd'),
            'verification_mode': source_payload.get('inference_verification_mode'),
        }
    return {}

def _build_recovery_summary(*, execution_receipt: Mapping[str, Any], reliability_trace: Mapping[str, Any]) -> dict[str, Any]:
    return _build_recovery_summary_owner(execution_receipt=execution_receipt, reliability_trace=reliability_trace)


def _extract_decision_agi_payload(world_state: object) -> dict[str, Any]:
    if isinstance(world_state, Mapping):
        meta = _safe_dict(world_state.get("meta"))
    else:
        meta = _safe_dict(getattr(world_state, "meta", {}))
    payload = _safe_dict(meta.get("decision_agi"))
    if payload:
        return payload
    summary = _safe_dict(meta.get("decision_agi_summary"))
    return {"summary": summary} if summary else {}


def _planning_ttl_from_horizon(horizon: str) -> int | None:
    normalized = str(horizon or "").strip().lower()
    if normalized == "day":
        return 1
    if normalized == "week":
        return 7
    if normalized == "month":
        return 30
    return None


def _decrement_planning_ttl(value: object) -> int | None:
    current = _safe_int(value)
    if current is None:
        return None
    return max(int(current) - 1, 0)


def _compact_decision_agi_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = _safe_dict(payload)
    summary = _safe_dict(data.get("summary"))
    selected_goal = _safe_dict(data.get("selected_goal"))
    selected_goal_name = str(selected_goal.get("goal") or summary.get("selected_goal") or "").strip()
    selected_goal_family = str(selected_goal.get("goal_family") or summary.get("selected_goal_family") or "").strip()
    strategy_hints = []
    for item in _safe_list(data.get("strategy_hints") or summary.get("strategy_hints"))[:8]:
        hint = _safe_dict(item)
        if hint:
            strategy_hints.append(hint)
    signal_count_raw = data.get("opportunity_signals")
    signal_count = len(_safe_list(signal_count_raw)) if signal_count_raw is not None else (_safe_int(summary.get("signal_count")) or 0)
    planning_horizon = str(data.get("planning_horizon") or summary.get("planning_horizon") or "").strip()
    incoming_ttl = data.get("planning_ttl")
    if incoming_ttl is None:
        incoming_ttl = summary.get("planning_ttl")
    planning_ttl = _decrement_planning_ttl(incoming_ttl)
    if planning_ttl is None:
        planning_ttl = _planning_ttl_from_horizon(planning_horizon)
    out = {
        "selected_goal": selected_goal_name,
        "selected_goal_family": selected_goal_family,
        "planning_horizon": planning_horizon,
        "planning_ttl": planning_ttl,
        "signal_count": int(signal_count),
        "strategy_hints": strategy_hints,
        "reasoning_mode": str(data.get("reasoning_mode") or summary.get("reasoning_mode") or "").strip(),
        "suppressed_reasons": list(data.get("suppressed_reasons") or summary.get("suppressed_reasons") or ()),
        "no_second_brain": True,
    }
    return {key: value for key, value in out.items() if value not in ("", None) and value != []}


def _normalize_approval_context(
    *,
    action: Mapping[str, Any],
    execution_receipt: Mapping[str, Any],
    approval_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return _normalize_approval_context_owner(
        action=action,
        execution_receipt=execution_receipt,
        approval_context=approval_context,
    )


def _build_approval_handoff(*, action: Mapping[str, Any], approval_context: Mapping[str, Any], next_tier: Mapping[str, Any]) -> dict[str, Any]:
    return _build_approval_handoff_owner(action=action, approval_context=approval_context, next_tier=next_tier)



__all__ = ['CANON_CLOSED_LOOP_ORCHESTRATOR_SUPPORT', '_safe_dict', '_safe_list', '_safe_int', '_stable_reliability_trace', '_economic_event_id', '_apply_economic_history_to_state', '_extract_inference_runtime_context', '_build_recovery_summary', '_extract_decision_agi_payload', '_planning_ttl_from_horizon', '_decrement_planning_ttl', '_compact_decision_agi_payload', '_normalize_approval_context', '_build_approval_handoff']
