from __future__ import annotations

from typing import Any

from application.decision_runtime.emission import (
    archive_envelope as archive_envelope_safe,
)
from application.decision_runtime.emission import (
    emit_decision_issued,
    emit_trace,
    emit_world_model_pinned,
)
from application.decision_runtime.flow import (
    build_archive_envelope,
    build_envelope,
    build_payload,
)
from application.decision_runtime.runtime import (
    apply_state_constraints,
    build_trace,
    extract_correlation_key,
    select_and_propose,
    validate_and_gate_action,
)
from application.decision_state.state_enrichment import (
    enrich_state_with_world_model,
    extract_actor_id,
    extract_product_metadata,
    extract_tenant_id,
)
from core.experiments.assignment import ExperimentArm
from core.observability.perf import Span, emit_sla_violation
from core.observability.throttled_logger import exception_throttled


def run_decision(
    *,
    core: Any,
    state: Any,
    envelope_version: int,
    logger: Any,
) -> Any:
    correlation_key = extract_correlation_key(state)
    state = enrich_state_with_world_model(
        state=state,
        world_model=core._world_model,
    )
    user_id, trace, pinned_world_model_meta = build_trace(
        state=state,
        issuer_id=core._issuer_id,
        envelope_version=envelope_version,
    )
    state = apply_state_constraints(
        state=state,
        trace=trace,
        user_id=str(user_id),
    )
    with Span(
        event_log=core._events,
        stage="decide_total",
        user_id=user_id,
        correlation_key=str(correlation_key) if correlation_key else None,
    ):
        with Span(
            event_log=core._events,
            stage="router",
            user_id=user_id,
            correlation_key=str(correlation_key) if correlation_key else None,
            extra={},
        ) as span_router:
            policy, out = select_and_propose(
                selector=core._selector,
                state=state,
                trace=trace,
            )
        span_router.extra = {"policy_id": getattr(policy, "id", "")}
        _emit_router_sla(
            core=core,
            user_id=user_id,
            correlation_key=correlation_key,
            span_router=span_router,
            logger=logger,
        )

        _product_meta, product_id, domain, product_version = (
            extract_product_metadata(state)
        )
        tenant_id = extract_tenant_id(state)
        actor_id = extract_actor_id(state)
        tagged, payload = build_payload(
            state=state,
            out=out,
            pinned_world_model_meta=pinned_world_model_meta,
            tenant_id=tenant_id,
            product_id=product_id,
            domain=domain,
            product_version=product_version,
            actor_id=actor_id,
        )
        action_schema_version = validate_and_gate_action(
            schemas=core._schemas,
            state=state,
            out=out,
            payload=payload,
            user_id=str(user_id),
            events=core._events,
            trace=trace,
        )
        built = build_envelope(
            state=state,
            out=out,
            payload=payload,
            policy_id=getattr(policy, "id", "") or "",
            keyring=core._keyring,
            issuer_id=core._issuer_id,
            ttl_ms=core._ttl_ms,
            action_schema_version=int(action_schema_version),
            envelope_version=envelope_version,
        )
        _record_live_canary_assignment(
            core=core,
            state=state,
            policy=policy,
            out=out,
            built=built,
            tenant_id=str(tenant_id),
            subject_id=str(actor_id or user_id),
            expected_cost=float(payload.get("expected_cost") or 0.0),
        )
        core._snapshots.put(built.decision.snapshot_id, built.state_bytes)
        archive_env = build_archive_envelope(
            archive_envelope=built.envelope,
            built=built,
            state=state,
            pinned_world_model_meta=pinned_world_model_meta,
            logger=logger,
        )
        archive_envelope_safe(
            archive=core._archive,
            events=core._events,
            env=archive_env,
            decision_id=str(built.decision.decision_id),
            user_id=str(user_id),
            correlation_id=str(built.decision.correlation_id),
        )
        emit_decision_issued(
            events=core._events,
            user_id=user_id,
            built=built,
            tagged=tagged,
            correlation_key=str(correlation_key) if correlation_key else None,
        )
        emit_world_model_pinned(
            events=core._events,
            user_id=str(user_id),
            decision_id=str(built.decision.decision_id),
            correlation_id=str(built.decision.correlation_id),
            world_model_meta=pinned_world_model_meta,
            issuer_id=core._issuer_id,
        )
        emit_trace(
            events=core._events,
            trace=trace,
            user_id=user_id,
            decision_id=str(built.decision.decision_id),
            correlation_id=str(built.decision.correlation_id),
        )
        try:
            core.dispatch_shadow(
                state=state,
                production_envelope=built.envelope,
                production_policy_id=str(getattr(policy, "id", "")),
            )
        except Exception:
            exception_throttled(
                logger,
                key=f"{user_id}|shadow_observer",
                msg=f"decision_core: shadow observer failed user={user_id}",
            )
        return built.envelope


def _policy_id(value: Any) -> str:
    return str(
        getattr(value, "policy_id", None)
        or getattr(value, "id", None)
        or ""
    )


def _active_policy_id(core: Any) -> str:
    registry = getattr(getattr(core, "_selector", None), "_registry", None)
    for name in ("active_ref", "active"):
        getter = getattr(registry, name, None)
        if not callable(getter):
            continue
        try:
            active = getter()
        except Exception:
            continue
        policy_id = _policy_id(active)
        if policy_id:
            return policy_id
    return ""


def _state_field(state: Any, name: str) -> Any:
    value = state.get(name) if isinstance(state, dict) else getattr(state, name, None)
    if value is not None:
        return value
    meta = state.get("meta") if isinstance(state, dict) else getattr(state, "meta", None)
    return meta.get(name) if isinstance(meta, dict) else None


def _state_flag(state: Any, name: str) -> bool:
    value = _state_field(state, name)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _record_live_canary_assignment(
    *,
    core: Any,
    state: Any,
    policy: Any,
    out: Any,
    built: Any,
    tenant_id: str,
    subject_id: str,
    expected_cost: float,
) -> None:
    coordinator = getattr(core, "_live_canary", None)
    if coordinator is None or coordinator.live_rollout_pct() <= 0:
        return

    selected_policy_id = _policy_id(policy)
    action = str(getattr(out, "action", ""))
    purpose = str(_state_field(state, "purpose") or "").strip()
    assignment = coordinator.assign(
        tenant_id=tenant_id,
        subject_id=subject_id,
        decision_id=str(built.decision.decision_id),
        correlation_id=str(built.decision.correlation_id),
        production_policy_id=_active_policy_id(core),
        action=action,
        purpose=purpose,
        eligible=_state_flag(
            state,
            coordinator.policy.eligibility_state_key,
        ),
        expected_cost=expected_cost,
    )
    selected_candidate = selected_policy_id == coordinator.candidate_policy_id
    if not assignment.eligible:
        if selected_candidate:
            raise RuntimeError("LIVE_CANARY_INELIGIBLE_CANDIDATE_SELECTED")
        return

    expected_arm = (
        ExperimentArm.CANDIDATE
        if selected_candidate
        else ExperimentArm.CONTROL
    )
    if assignment.arm is not expected_arm:
        raise RuntimeError("LIVE_CANARY_ASSIGNMENT_MISMATCH")
    coordinator.assert_candidate_action_allowed(assignment, action=action)


def _emit_router_sla(
    *,
    core: Any,
    user_id: str,
    correlation_key: Any,
    span_router: Any,
    logger: Any,
) -> None:
    import time

    try:
        emit_sla_violation(
            event_log=core._events,
            stage="router",
            duration_ms=int(
                (time.perf_counter_ns() - span_router._t0_ns) / 1_000_000
            ),
            user_id=user_id,
            decision_id=None,
            correlation_id=None,
            correlation_key=str(correlation_key) if correlation_key else None,
        )
    except Exception:
        exception_throttled(
            logger,
            key=f"{user_id}|sla_violation",
            msg=f"decision_core: emit_sla_violation failed user={user_id}",
        )
