from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from typing import Any
from collections.abc import Mapping

from observability.distributed_trace_context import trace_context_from_envelope, trace_context_scope
from observability.execution_span import execution_span
from observability.execution_trace_contract import TraceStage
from runtime.decision import DecisionEnvelope
from runtime.execution.context import executor_context
from runtime.execution.executor_entrypoint_bundle import build_executor_entrypoint_bundle
from runtime.execution.executor_result import ExecutionResult
from runtime.execution.executor_stages import preflight_and_verify
from runtime.execution.governance_runtime import GovernanceExecutionBlocked
from runtime.execution.operational_budget_runtime import OperationalBudgetBlocked
from runtime.safety_controls import record_execution_outcome


def _generated_at_ms(env: DecisionEnvelope) -> int:
    payload = getattr(getattr(env, "decision", None), "payload", {}) or {}
    if isinstance(payload, Mapping):
        for key in ("generated_at_ms", "now_ms", "timestamp_ms"):
            value = payload.get(key)
            try:
                if value is not None:
                    return int(value)
            except Exception:
                continue
    return 0


def _record_runtime_trace_story(*, executor, env: DecisionEnvelope, trace_kind: str, stage: str, **fields: object) -> None:
    observability = getattr(executor, "_runtime_observability", None)
    if observability is None:
        return
    method_name = {
        "execution": "record_execution_trace",
        "recovery": "record_recovery_trace",
        "decision": "record_decision_trace",
        "world_state": "record_world_state_trace",
        "effect": "record_effect_trace",
    }.get(str(trace_kind), "record_trace_story")
    method = getattr(observability, method_name, None)
    if not callable(method):
        return
    payload = {k: v for k, v in dict(fields).items() if isinstance(v, (str, int, float))}
    payload.setdefault("decision_id", str(getattr(getattr(env, "decision", None), "decision_id", "") or ""))
    payload.setdefault("action", str(getattr(getattr(env, "decision", None), "action", "") or ""))
    try:
        if method_name == "record_trace_story":
            method(trace_name="runtime_executor", stage=stage, generated_at_ms=_generated_at_ms(env), trace_kind=trace_kind, **payload)
        else:
            method(trace_name="runtime_executor", stage=stage, generated_at_ms=_generated_at_ms(env), **payload)
    except Exception:
        return


def trace_context_for_env(*, env: DecisionEnvelope, safe_dict) -> object | None:
    payload = safe_dict(getattr(getattr(env, 'decision', None), 'payload', {}) or {})
    tenant_id = str(payload.get('tenant_id') or payload.get('tenant') or '').strip()
    if not tenant_id:
        return None
    try:
        return trace_context_from_envelope(
            env,
            tenant_id=tenant_id,
            user_id=str(payload.get('user_id') or 'system'),
            executor_name='RuntimeExecutor',
            component='runtime.executor',
        )
    except Exception:
        return None


def execute_with_trace(*, executor, env: DecisionEnvelope) -> ExecutionResult:
    trace_context = executor._trace_context_for_env(env)
    trace_id = getattr(trace_context, 'trace_id', None)
    payload = executor._safe_dict(getattr(getattr(env, 'decision', None), 'payload', {}) or {})
    with trace_context_scope(trace_context):
        executor._append_decision_trace(env, trace_id)
        _record_runtime_trace_story(executor=executor, env=env, trace_kind='execution', stage='started', trace_id=str(trace_id or ''))
        executor._record_action_audit(env=env, trace_id=trace_id, stage='runtime.execute', status='started')
        if hasattr(executor, '_record_inference_runtime_trace'):
            executor._record_inference_runtime_trace(env=env, stage='selected')
        executor._record_connector_runtime_event(env=env, status='runtime_started')
        try:
            entrypoint_bundle = build_executor_entrypoint_bundle(
                event_log=executor._events,
                snapshot_store=executor._snapshot_store,
                executor_context_cm=executor_context,
            )
            result = entrypoint_bundle.run(executor=executor, env=env)
            record_execution_outcome(
                action=str(getattr(env.decision, 'action', '') or ''),
                payload=payload,
                success=bool(getattr(result, 'ok', False)),
            )
            executor._record_action_audit(
                env=env,
                trace_id=trace_id,
                stage='runtime.execute',
                status='succeeded' if getattr(result, 'ok', False) else 'failed',
                payload={'error': getattr(result, 'error', None), 'ok': bool(getattr(result, 'ok', False))},
            )
            executor._record_connector_runtime_event(
                env=env,
                status='runtime_succeeded' if getattr(result, 'ok', False) else 'runtime_failed',
                payload={'ok': bool(getattr(result, 'ok', False)), 'error': getattr(result, 'error', None)},
            )
            _record_runtime_trace_story(
                executor=executor,
                env=env,
                trace_kind='execution',
                stage='succeeded' if getattr(result, 'ok', False) else 'failed',
                trace_id=str(trace_id or ''),
                ok=1 if getattr(result, 'ok', False) else 0,
            )
            return result
        except (OperationalBudgetBlocked, GovernanceExecutionBlocked) as exc:
            executor._record_action_audit(env=env, trace_id=trace_id, stage='runtime.execute', status='blocked', payload=dict(exc.output))
            if hasattr(executor, '_record_inference_runtime_trace'):
                executor._record_inference_runtime_trace(env=env, stage='blocked')
            executor._record_connector_runtime_event(env=env, status='runtime_blocked', payload=dict(exc.output))
            _record_runtime_trace_story(executor=executor, env=env, trace_kind='execution', stage='blocked', trace_id=str(trace_id or ''), error=str(exc.error))
            return ExecutionResult(
                ok=False,
                output=dict(exc.output),
                error=str(exc.error),
                decision_id=str(env.decision.decision_id),
                correlation_id=str(env.decision.correlation_id),
            )
        except Exception as exc:
            try:
                record_execution_outcome(
                    action=str(getattr(env.decision, 'action', '') or ''),
                    payload=payload,
                    success=False,
                )
            except Exception:
                pass
            executor._record_action_audit(
                env=env,
                trace_id=trace_id,
                stage='runtime.execute',
                status='failed',
                payload={'error': type(exc).__name__, 'message': str(exc)},
            )
            executor._record_connector_runtime_event(
                env=env,
                status='runtime_exception',
                payload={'error': type(exc).__name__, 'message': str(exc)},
            )
            if hasattr(executor, '_record_inference_runtime_trace'):
                executor._record_inference_runtime_trace(env=env, stage='exception')
            _record_runtime_trace_story(executor=executor, env=env, trace_kind='execution', stage='exception', trace_id=str(trace_id or ''), error=type(exc).__name__)
            raise


def execute_core_flow(*, executor, env: DecisionEnvelope, depth: int, timescale) -> ExecutionResult:
    reliability = getattr(executor, '_reliability', None)
    payload = executor._safe_dict(getattr(getattr(env, 'decision', None), 'payload', {}) or {})
    isolation_cm = executor._tenant_runtime_context(env=env, payload=payload)
    tenant_id = str(payload.get('tenant_id') or payload.get('tenant') or '').strip()
    run_id = str(payload.get('run_id') or getattr(env.decision, 'decision_id', '') or '').strip()
    span_cm = execution_span(
        stage=TraceStage.EXECUTION,
        tenant_id=tenant_id,
        run_id=run_id,
        event_log=executor._events,
        execution_trace_store=getattr(executor, '_execution_trace_store', None),
        decision_id=str(getattr(env.decision, 'decision_id', '') or '') or None,
        correlation_id=str(getattr(env.decision, 'correlation_id', '') or '') or None,
        action_id=str(payload.get('action_id') or getattr(env.decision, 'decision_id', '') or '') or None,
        executor_name='RuntimeExecutor',
        component='runtime.executor',
        user_id=str(payload.get('user_id') or 'system'),
        start_payload={'depth': int(depth), 'timescale': str(timescale.value if hasattr(timescale, 'value') else timescale)},
        success_payload={'dispatch': 'completed'},
        failure_payload_builder=lambda exc: {'error': type(exc).__name__, 'message': str(exc)},
    ) if tenant_id and run_id else nullcontext()
    try:
        with isolation_cm, span_cm:
            resolution_result = executor._apply_reliability_gate(env)
            if resolution_result is not None:
                return resolution_result
            preflight_and_verify(executor=executor, env=env, timescale=timescale)
            budget_verdict = executor._enforce_runtime_budget_and_blast_radius(env)
            result = executor._dispatch(env, depth=depth, enqueue=True)
            record_execution_outcome(
                action=str(getattr(env.decision, 'action', '') or ''),
                payload=payload,
                success=bool(getattr(result, 'ok', False)),
            )
            if getattr(result, 'ok', False):
                enriched_output = executor._safe_dict(getattr(result, 'output', None))
                if budget_verdict is not None:
                    enriched_output['tenant_budget'] = {
                        'allowed': bool(getattr(budget_verdict, 'allowed', False)),
                        'reason': str(getattr(budget_verdict, 'reason', '')),
                        'tenant_id': str(getattr(budget_verdict, 'tenant_id', '')),
                        'violations': list(getattr(budget_verdict, 'violations', ()) or ()),
                        'consumed': bool(getattr(budget_verdict, 'consumed', False)),
                    }
                return replace(
                    result,
                    output=executor._attach_effect_delivery_metadata(env=env, output=enriched_output),
                )
            return result
    except Exception as exc:
        try:
            record_execution_outcome(
                action=str(getattr(env.decision, 'action', '') or ''),
                payload=payload,
                success=False,
            )
        except Exception:
            pass
        if reliability is not None:
            try:
                reliability.mark_failed(env, reason=f'runtime_execute:{type(exc).__name__}')
                reliability.append_checkpoint(
                    env,
                    stage='failed',
                    checkpoint_id=f"failed:{getattr(env.decision, 'decision_id', 'unknown')}",
                    payload={'reason': f'runtime_execute:{type(exc).__name__}'},
                )
            except Exception as checkpoint_exc:
                executor._logger.warning('reliability.append_checkpoint_failed', exc_info=checkpoint_exc)
        raise
