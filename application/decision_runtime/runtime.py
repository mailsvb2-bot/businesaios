from __future__ import annotations

from collections.abc import Mapping as AbcMapping
from math import isfinite
from typing import Any

from application.decision_policy.policy_stage import propose_action
from application.decision_runtime.gate import gate_action_or_raise
from application.decision_state.state_enrichment import (
    apply_causal_constraints,
    apply_price_constraints,
)
from application.decision_state.world_model_metadata import (
    extract_world_model_metadata,
    summarize_pricing_world_state,
)
from core.observability.perf import emit_sla_violation
from core.observability.throttled_logger import exception_throttled


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


def _canonical_goal_context(state: Any) -> dict[str, Any]:
    raw_meta = state.get("meta") if isinstance(state, AbcMapping) else getattr(state, "meta", {})
    return _safe_dict(_safe_dict(raw_meta or {}).get("canonical_goal"))


def _goal_conflict_view(state: Any) -> dict[str, Any]:
    return _safe_dict(_canonical_goal_context(state).get("conflicts"))


def _guard_metric_view(state: Any) -> list[dict[str, Any]]:
    constraints = _safe_dict(_canonical_goal_context(state).get("constraints"))
    return [
        _safe_dict(item)
        for item in list(constraints.get("guard_metrics") or ())
        if isinstance(item, AbcMapping)
    ]


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


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
    canonical_goal = _canonical_goal_context(state)
    if canonical_goal:
        goal = _safe_dict(canonical_goal.get("goal"))
        conflicts = _goal_conflict_view(state)
        trace.try_add_step(
            name="canonical_goal_objective",
            input={},
            output={
                "goal_id": str(goal.get("goal_id") or ""),
                "metric": goal.get("metric"),
                "baseline": goal.get("baseline"),
                "target": goal.get("target"),
                "priority": goal.get("priority"),
                "guard_metrics": _guard_metric_view(state),
                "has_conflicts": bool(conflicts.get("has_conflicts")),
                "deterministic_only": True,
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


def _enforce_canonical_goal_lifecycle_gate(
    *,
    state: Any,
    action: str,
    user_id: str,
    events: Any,
    trace: Any,
) -> None:
    canonical_goal = _canonical_goal_context(state)
    if not canonical_goal:
        return
    goal = _safe_dict(canonical_goal.get("goal"))
    goal_id = str(goal.get("goal_id") or "").strip()
    lifecycle_status = str(goal.get("lifecycle_status") or "").strip().lower()
    if not goal_id or not lifecycle_status or lifecycle_status == "active":
        return
    allowed = str(action or "") in {"noop", "noop@v1"}
    diagnostics = {
        "goal_id": goal_id,
        "lifecycle_status": lifecycle_status,
        "action": str(action or ""),
        "allowed": allowed,
        "reason": "canonical_goal_terminal",
    }
    trace.try_add_step(
        name="canonical_goal_lifecycle_gate",
        input={},
        output=diagnostics,
    )
    if allowed:
        return
    emit = getattr(events, "emit", None)
    if callable(emit):
        emit(
            event_type="decision_blocked",
            source="decision_core",
            user_id=str(user_id),
            decision_id="",
            correlation_id="",
            payload=diagnostics,
        )
    raise RuntimeError("DECISION_BLOCKED:canonical_goal_terminal")


def _enforce_canonical_goal_conflict_gate(
    *,
    state: Any,
    action: str,
    user_id: str,
    events: Any,
    trace: Any,
) -> None:
    conflicts = _goal_conflict_view(state)
    if not bool(conflicts.get("has_conflicts")):
        return
    allowed = str(action or "") in {"noop", "noop@v1"}
    goal = _safe_dict(_canonical_goal_context(state).get("goal"))
    diagnostics = {
        "goal_id": str(goal.get("goal_id") or ""),
        "action": str(action or ""),
        "allowed": allowed,
        "goal_goal_conflict_count": len(list(conflicts.get("goal_goal") or ())),
        "goal_constraint_conflict_count": len(list(conflicts.get("goal_constraint") or ())),
        "reason": "canonical_goal_conflict",
    }
    trace.try_add_step(name="canonical_goal_conflict_gate", input={}, output=diagnostics)
    if allowed:
        return
    emit = getattr(events, "emit", None)
    if callable(emit):
        emit(
            event_type="decision_blocked",
            source="decision_core",
            user_id=str(user_id),
            decision_id="",
            correlation_id="",
            payload=diagnostics,
        )
    raise RuntimeError("DECISION_BLOCKED:canonical_goal_conflict")


def _enforce_canonical_guard_metrics(
    *,
    state: Any,
    proposal: Any,
    user_id: str,
    events: Any,
    trace: Any,
) -> None:
    action = str(getattr(proposal, "action", "") or "")
    if action in {"noop", "noop@v1"}:
        return
    ranking = _safe_dict(getattr(proposal, "ranking", {}) or {})
    evaluations: list[dict[str, Any]] = []
    blocking_reason = ""
    for guard in _guard_metric_view(state):
        if str(guard.get("severity") or "").lower() != "hard":
            continue
        comparison = str(guard.get("comparison") or "").lower()
        if not comparison:
            continue
        constraint_id = str(guard.get("constraint_id") or "")
        metric = str(guard.get("metric") or "")
        threshold = _finite_number(guard.get("threshold"))
        if not constraint_id or not metric or comparison not in {"lte", "gte"} or threshold is None:
            blocking_reason = blocking_reason or "canonical_guard_metric_contract_invalid"
            evaluations.append({"constraint_id": constraint_id, "metric": metric, "comparison": comparison, "status": "invalid_contract"})
            continue
        ranking_key = f"guard_value:{constraint_id}"
        predicted = _finite_number(ranking.get(ranking_key))
        if predicted is None:
            blocking_reason = blocking_reason or "canonical_guard_metric_projection_missing"
            evaluations.append({"constraint_id": constraint_id, "metric": metric, "comparison": comparison, "threshold": threshold, "ranking_key": ranking_key, "status": "missing"})
            continue
        satisfied = (comparison == "lte" and predicted <= threshold) or (comparison == "gte" and predicted >= threshold)
        evaluations.append({"constraint_id": constraint_id, "metric": metric, "comparison": comparison, "threshold": threshold, "predicted": predicted, "ranking_key": ranking_key, "status": "satisfied" if satisfied else "violated"})
        if not satisfied:
            blocking_reason = "canonical_guard_metric_violation"
    if not evaluations:
        return
    diagnostics = {
        "goal_id": str(_safe_dict(_canonical_goal_context(state).get("goal")).get("goal_id") or ""),
        "action": action,
        "allowed": not bool(blocking_reason),
        "reason": blocking_reason or "canonical_guard_metrics_satisfied",
        "evaluations": evaluations,
    }
    trace.try_add_step(name="canonical_guard_metric_gate", input={}, output=diagnostics)
    if not blocking_reason:
        return
    emit = getattr(events, "emit", None)
    if callable(emit):
        emit(event_type="decision_blocked", source="decision_core", user_id=str(user_id), decision_id="", correlation_id="", payload=diagnostics)
    raise RuntimeError(f"DECISION_BLOCKED:{blocking_reason}")


def validate_and_gate_action(
    *,
    schemas: Any,
    state: Any,
    out: Any,
    user_id: str,
    events: Any,
    trace: Any,
    payload: dict[str, Any] | None = None,
) -> int:
    action_payload = (
        dict(payload)
        if isinstance(payload, dict)
        else (dict(out.payload) if isinstance(out.payload, dict) else {})
    )
    action_schema_version = schemas.validate(out.action, action_payload)
    _enforce_canonical_goal_lifecycle_gate(
        state=state,
        action=out.action,
        user_id=str(user_id),
        events=events,
        trace=trace,
    )
    _enforce_canonical_goal_conflict_gate(
        state=state,
        action=out.action,
        user_id=str(user_id),
        events=events,
        trace=trace,
    )
    _enforce_canonical_guard_metrics(
        state=state,
        proposal=out,
        user_id=str(user_id),
        events=events,
        trace=trace,
    )
    trace.try_add_step(
        name="schema_validate",
        input={"action": getattr(out, "action", "")},
        output={"action_schema_version": int(action_schema_version)},
    )
    try:
        product_meta = getattr(state, "product_metadata", None)
        if not isinstance(product_meta, dict):
            product_meta = {}
        tid_for_gate = str(
            action_payload.get("tenant_id")
            or product_meta.get("tenant_id")
            or getattr(state, "tenant_id", "")
            or ""
        )
        uid_for_gate = str(action_payload.get("actor_id") or user_id)
        gate_action_or_raise(
            action=out.action,
            payload=action_payload,
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
