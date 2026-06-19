from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from typing import Any

from application.decision_policy.policy_stage import propose_action
from application.decision_state.state_enrichment import (
    apply_causal_constraints,
    apply_price_constraints,
)
from application.decision_state.world_model_metadata import (
    extract_world_model_metadata,
    summarize_pricing_world_state,
)
from core.observability.perf import Span, emit_sla_violation
from core.observability.throttled_logger import exception_throttled


def gate_action_or_raise(**kwargs: Any) -> None:
    core_api = __import__("core.ai.decision_core", fromlist=["gate_action_or_raise"])
    core_api.gate_action_or_raise(**kwargs)


def extract_correlation_key(state: Any) -> str | None:
    try:
        meta = dict(getattr(state, "meta", {}) or {})
        value = meta.get("correlation_key") or meta.get("correlation")
        return str(value) if value else None
    except Exception:
        return None


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, AbcMapping):
        return dict(value)
    return {}


def _extract_decision_agi_summary(state: Any) -> dict[str, Any]:
    try:
        meta = dict(getattr(state, "meta", {}) or {})
    except Exception:
        meta = {}
    payload = meta.get("decision_agi_summary")
    return dict(payload) if isinstance(payload, dict) else {}


def _extract_decision_agi_payload(state: Any) -> dict[str, Any]:
    return _safe_dict(_safe_dict(getattr(state, "meta", {}) or {}).get("decision_agi"))


def build_trace(*, state: Any, issuer_id: str, envelope_version: int) -> tuple[str, Any, dict[str, Any]]:
    from core.decision.ai_decision_trace import TraceBuilder
    from execution.agi_reasoning_contract import compact_goal_for_trace, compact_strategy_hint_for_trace

    user_id = getattr(state, "user_id", "unknown") or "unknown"
    correlation_key = extract_correlation_key(state)
    trace = TraceBuilder(
        user_id=str(user_id),
        correlation_id=str(correlation_key) if correlation_key else None,
    )
    trace.meta(issuer_id=issuer_id, envelope_version=envelope_version)

    world_model_meta = extract_world_model_metadata(state=state)
    if world_model_meta:
        trace.try_add_step(
            name="world_model_metadata",
            input={},
            output=dict(world_model_meta),
        )

    pricing_summary = summarize_pricing_world_state(state=state)
    if pricing_summary:
        trace.try_add_step(
            name="pricing_world_state_summary",
            input={},
            output=dict(pricing_summary),
        )

    decision_agi_summary = _extract_decision_agi_summary(state)
    decision_agi_payload = _extract_decision_agi_payload(state)
    if decision_agi_summary or decision_agi_payload:
        selected_goal = compact_goal_for_trace(
            _safe_dict(decision_agi_payload.get("selected_goal")) or {
                "goal": decision_agi_summary.get("selected_goal"),
                "goal_family": decision_agi_summary.get("selected_goal_family"),
            }
        )
        raw_hints = list(decision_agi_payload.get("strategy_hints") or decision_agi_summary.get("strategy_hints") or ())
        compact_hints = []
        for item in raw_hints[:6]:
            hint_payload = compact_strategy_hint_for_trace(_safe_dict(item))
            if hint_payload:
                compact_hints.append(hint_payload)
        trace.try_add_step(
            name="decision_agi_summary",
            input={},
            output={
                "selected_goal": selected_goal,
                "planning_horizon": str(decision_agi_summary.get("planning_horizon") or decision_agi_payload.get("planning_horizon") or ""),
                "signal_count": int(decision_agi_summary.get("signal_count") or len(list(decision_agi_payload.get("opportunity_signals") or ()))),
                "strategy_hints": compact_hints,
                "reasoning_mode": str(decision_agi_summary.get("reasoning_mode") or decision_agi_payload.get("reasoning_mode") or ""),
                "no_second_brain": True,
            },
        )
    return str(user_id), trace, dict(world_model_meta or {})


def apply_state_constraints(*, state: Any, trace: Any, user_id: str) -> Any:
    state = apply_causal_constraints(state=state, trace=trace, user_id=str(user_id))
    state = apply_price_constraints(state=state, trace=trace, user_id=str(user_id))
    return state


def select_and_propose(*, selector: Any, state: Any, trace: Any) -> tuple[Any, Any]:
    policy = selector.select(state)
    trace.try_add_step(
        name="select_policy",
        input={},
        output={"policy_id": getattr(policy, "id", "")},
    )
    out = propose_action(policy=policy, state=state, trace=trace)
    trace.try_add_step(
        name="policy_propose",
        input={},
        output={"action": getattr(out, "action", ""), "policy_id": getattr(policy, "id", "")},
    )
    return policy, out


def validate_and_gate_action(*, schemas: Any, state: Any, out: Any, user_id: str, events: Any, trace: Any) -> int:
    action_schema_version = schemas.validate(out.action, out.payload)
    trace.try_add_step(
        name="schema_validate",
        input={"action": getattr(out, "action", "")},
        output={"action_schema_version": int(action_schema_version)},
    )
    try:
        product_meta = getattr(state, "product_metadata", None)
        if not isinstance(product_meta, dict):
            product_meta = {}
        tid_for_gate = str(product_meta.get("tenant_id") or getattr(state, "tenant_id", "") or "")
        payload = dict(out.payload) if isinstance(out.payload, dict) else {}
        uid_for_gate = str(payload.get("user_id") or user_id)
        gate_action_or_raise(
            action=out.action,
            payload=payload,
            tenant_id=tid_for_gate,
            user_id=uid_for_gate,
            event_log=events,
            trace=trace,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        events.emit(
            event_type="decision_blocked",
            source="decision_core",
            user_id=user_id,
            decision_id="",
            correlation_id="",
            payload={
                "action": getattr(out, "action", ""),
                "reason": "action_safety_gate_error",
                "error": exc.__class__.__name__,
            },
        )
        raise RuntimeError("DECISION_BLOCKED:action_safety_gate_error") from exc
    return int(action_schema_version)


def _emit_router_sla(*, core: Any, user_id: str, correlation_key: Any, span_router: Any, logger: Any) -> None:
    import time

    try:
        emit_sla_violation(
            event_log=core._events,
            stage="router",
            duration_ms=int((time.perf_counter_ns() - span_router._t0_ns) / 1_000_000),
            user_id=user_id,
            decision_id=None,
            correlation_id=None,
            correlation_key=str(correlation_key) if correlation_key else None,
        )
    except Exception:
        exception_throttled(
            logger,
            key=f'{user_id}|sla_violation',
            msg=f'decision_core: emit_sla_violation failed user={user_id}',
        )
