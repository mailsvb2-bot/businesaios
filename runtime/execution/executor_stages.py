from __future__ import annotations

from typing import Any

from governance.time_scale import TimeScale
from runtime.execution.dispatcher import effect_succeeded
from runtime.execution.execution_contract_lock import commit_verified_execution, verify_execution_contract
from runtime.execution.executor_audit import emit_deployment_proposed, emit_effect_window, emit_reward_observed
from runtime.execution.executor_commit import build_delivery_metadata, enqueue_once
from runtime.execution.executor_core import assert_timescale_allowed, enforce_safe_mode, load_world
from runtime.execution.governance_runtime import review_governance_execution
from runtime.execution.operational_budget_runtime import review_operational_budget
from runtime.execution.world_model_pin_runtime import check_and_emit_world_model_pin
from runtime.observability.telemetry import correlation_key_scope
from runtime.observability.tracing import span_with_sla
from runtime.security.capability_gate import clear_effect_capability, set_effect_capability
from runtime.security.product_action_gate import review_action


def _checkpoint(*, executor: Any, env: Any, stage: str, payload: dict[str, Any] | None = None) -> None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return
    try:
        reliability.append_checkpoint(
            env,
            stage=stage,
            checkpoint_id=f"{stage}:{getattr(getattr(env, 'decision', None), 'decision_id', 'unknown')}",
            payload=dict(payload or {}),
        )
    except Exception:
        return


def _emit_operational_event(*, executor: Any, env: Any, event_type: str, payload: dict[str, Any]) -> None:
    events = getattr(executor, "_events", None)
    if events is None or not hasattr(events, "emit"):
        return
    try:
        events.emit(
            event_type=event_type,
            source="runtime.execution.executor_stages",
            user_id=(env.decision.payload or {}).get("user_id", "system") if isinstance(env.decision.payload, dict) else "system",
            decision_id=str(getattr(env.decision, "decision_id", "unknown")),
            correlation_id=str(getattr(env.decision, "correlation_id", "unknown")),
            payload=dict(payload),
        )
    except Exception:
        return


def _mark_execution_completed(*, executor: Any, env: Any) -> None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return
    try:
        reliability.mark_completed(env)
        _checkpoint(executor=executor, env=env, stage="completed", payload={"status": "ok"})
    except Exception:
        return


def _mark_execution_failed(*, executor: Any, env: Any, reason: str) -> None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return
    try:
        reliability.mark_failed(env, reason=reason)
        _checkpoint(executor=executor, env=env, stage="failed", payload={"reason": str(reason)})
    except Exception:
        return


def preflight_and_verify(*, executor: Any, env: Any, timescale: TimeScale) -> None:
    _checkpoint(executor=executor, env=env, stage="request", payload={"timescale": str(timescale.value if hasattr(timescale, "value") else timescale)})
    _checkpoint(executor=executor, env=env, stage="decision", payload={"action": str(env.decision.action)})
    enforce_safe_mode(action=str(env.decision.action))
    executor._constitution.assert_decision_envelope(env)
    assert_timescale_allowed(action=str(env.decision.action), timescale=timescale)
    _review_economic_layer(executor=executor, env=env)
    _review_product_capability(executor=executor, env=env)
    review_operational_budget(executor=executor, env=env)
    review_governance_execution(executor=executor, env=env)
    executor._guard.execute_once(env)
    _checkpoint(executor=executor, env=env, stage="executable_action", payload={"action": str(env.decision.action)})
    _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_preflight_passed", payload={"action": str(env.decision.action), "timescale": str(timescale.value if hasattr(timescale, 'value') else timescale)})



def _review_economic_layer(*, executor: Any, env: Any) -> None:
    if executor._economic_layer is None or executor._snapshot_store is None:
        return
    world = load_world(executor._snapshot_store, str(env.decision.snapshot_id))
    verdict = executor._economic_layer.review(world_state=world, decision_env=env)
    if verdict.allow:
        return
    if executor._events is not None:
        executor._events.emit(
            event_type="economic_layer_veto",
            source="governance.economic_layer",
            user_id="system",
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            payload={"reason": verdict.reason},
        )
    raise RuntimeError(f"ECONOMIC_LAYER_VETO:{verdict.reason or 'veto'}")



def _review_product_capability(*, executor: Any, env: Any) -> None:
    world = load_world(executor._snapshot_store, str(env.decision.snapshot_id))
    try:
        product = getattr(world, "product", None) if world is not None else None
    except Exception:
        product = None
    pg = review_action(product=product if isinstance(product, dict) else {}, action=str(env.decision.action))
    if pg.allow:
        return
    if executor._events is not None:
        executor._events.emit(
            event_type="product_capability_veto",
            source="runtime.product_gate",
            user_id=str(getattr(world, "user_id", "system") if world is not None else "system"),
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            payload={"reason": pg.reason, "action": str(env.decision.action), "product": product if isinstance(product, dict) else {}},
        )
    raise RuntimeError(pg.reason or "PRODUCT_CAPABILITY_VETO")



def dispatch_effects(*, executor: Any, env: Any, depth: int, enqueue: bool):
    ck = executor._extract_ck(str(env.decision.snapshot_id))
    if enqueue:
        enqueue_once(executor._outbox, decision=env.decision)
        queue_metadata = build_delivery_metadata(decision=env.decision, mode="enqueue", owner_id="runtime-executor")
        _checkpoint(executor=executor, env=env, stage="queue_dispatch", payload={"mode": "outbox", "enqueued": True, **queue_metadata})
        _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_outbox_enqueued", payload={"action": str(env.decision.action), "outbox_mode": "enqueue_once", **queue_metadata})
    if not executor._claim_or_skip_outbox(env):
        _checkpoint(executor=executor, env=env, stage="execution", payload={"status": "already_claimed"})
        _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_claim_skipped", payload={"reason": "already_claimed"})
        return executor._already_claimed_result(env)
    _checkpoint(executor=executor, env=env, stage="execution", payload={"enqueue": bool(enqueue), "claimed": True})
    check_and_emit_world_model_pin(
        event_log=executor._events,
        snapshot_store=executor._snapshot_store,
        decision=env.decision,
        issuer_id=getattr(executor, "_issuer_id", "runtime-executor"),
    )
    emit_effect_window(executor._events, opened=True, decision=env.decision)
    set_effect_capability(executor._cap_token)
    try:
        with correlation_key_scope(str(ck) if ck else None), span_with_sla(
            event_log=executor._events,
            stage="handler",
            user_id=(env.decision.payload or {}).get("user_id", "unknown") if isinstance(env.decision.payload, dict) else "unknown",
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
            correlation_key=str(ck) if ck else None,
        ):
            out = executor._handlers.dispatch(env.decision.action, env.decision.payload, executor._effects, env)
    except Exception as exc:
        _mark_execution_failed(executor=executor, env=env, reason=f"dispatch_exception:{type(exc).__name__}")
        _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_dispatch_failed", payload={"error_type": type(exc).__name__})
        raise
    finally:
        clear_effect_capability()
        emit_effect_window(executor._events, opened=False, decision=env.decision)
    if not effect_succeeded(out):
        _mark_execution_failed(executor=executor, env=env, reason="effect_failed")
        _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_effect_failed", payload={"action": str(env.decision.action)})
        raise RuntimeError("EFFECT_FAILED")
    verification_result = verify_execution_contract(executor=executor, env=env, output=out)
    committed_output = commit_verified_execution(executor=executor, env=env, output=out, verification_result=verification_result)
    _observe_reward_and_learning(executor=executor, env=env, out=committed_output, depth=depth)
    _mark_execution_completed(executor=executor, env=env)
    _emit_operational_event(executor=executor, env=env, event_type="runtime_executor_dispatch_succeeded", payload={"action": str(env.decision.action)})
    from runtime.execution.executor_result import ExecutionResult
    return ExecutionResult(ok=True, output=committed_output, error=None, decision_id=env.decision.decision_id, correlation_id=env.decision.correlation_id)



def _observe_reward_and_learning(*, executor: Any, env: Any, out: Any, depth: int) -> None:
    reward = None
    if executor._reward is not None:
        reward = float(executor._reward.observe(env, out))
        emit_reward_observed(executor._events, decision=env.decision, reward_engine=executor._reward, reward=float(reward))
    if executor._learning is None or reward is None:
        return
    details = executor._reward.last_details() if hasattr(executor._reward, 'last_details') else None
    ltv = None
    try:
        if isinstance(details, dict) and 'ltv' in details:
            ltv = float(details.get('ltv'))
    except Exception:
        ltv = None
    executor._learning.observe_reward(policy_id=str(env.decision.policy_id), reward=float(reward), ltv=ltv)
    if depth < executor._max_meta_depth:
        proposal = executor._learning.maybe_propose_deployment()
        if proposal:
            emit_deployment_proposed(executor._events, decision=env.decision, proposal=proposal)
