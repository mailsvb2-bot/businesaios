from __future__ import annotations

import logging
from typing import Any, Mapping

from connectors.platform.connector_observability import ConnectorExecutionEvent
from observability.execution_trace_contract import DecisionTraceEvent
from runtime.decision import DecisionEnvelope
from runtime.execution.executor_commit import _decision_tenant_id

logger = logging.getLogger(__name__)


def _generated_at_ms_from_env(*, env: DecisionEnvelope, safe_dict) -> int:
    payload = safe_dict(getattr(getattr(env, "decision", None), "payload", {}) or {})
    for key in ("generated_at_ms", "now_ms", "timestamp_ms"):
        value = payload.get(key)
        try:
            if value is not None:
                return int(value)
        except Exception:
            continue
    return 0


def append_decision_trace(*, store, env: DecisionEnvelope, trace_id: str | None, safe_dict) -> None:
    if store is None:
        return
    payload = safe_dict(getattr(getattr(env, "decision", None), "payload", {}) or {})
    tenant_id = str(payload.get("tenant_id") or payload.get("tenant") or "").strip()
    decision_id = str(getattr(getattr(env, "decision", None), "decision_id", "") or "").strip()
    if not tenant_id or not decision_id or not trace_id:
        return
    try:
        if hasattr(store, "get") and store.get(tenant_id=tenant_id, decision_id=decision_id) is not None:
            return
        store.append(
            DecisionTraceEvent(
                tenant_id=tenant_id,
                trace_id=str(trace_id),
                decision_id=decision_id,
                correlation_id=str(getattr(env.decision, "correlation_id", "") or "") or None,
                route_name="runtime.execute",
                selected_action=str(getattr(env.decision, "action", "") or payload.get("action_type") or ""),
                component="runtime.executor",
                payload={
                    "action": str(getattr(env.decision, "action", "") or ""),
                    "snapshot_id": str(getattr(env.decision, "snapshot_id", "") or ""),
                },
            )
        )
    except Exception as exc:
        logger.warning("runtime_executor_decision_trace_append_failed", exc_info=exc)


def record_action_audit(*, audit_log, env: DecisionEnvelope, trace_id: str | None, stage: str, status: str, payload: Mapping[str, Any] | None, safe_dict) -> None:
    if audit_log is None or not hasattr(audit_log, "record_stage"):
        return
    decision = getattr(env, "decision", None)
    payload_map = safe_dict(getattr(decision, "payload", {}) or {})
    tenant_id = str(payload_map.get("tenant_id") or _decision_tenant_id(decision) or "").strip()
    action_id = str(payload_map.get("action_id") or getattr(decision, "decision_id", "") or "").strip()
    action_type = str(getattr(decision, "action", "") or payload_map.get("action_type") or "").strip()
    if not tenant_id or not action_id or not action_type:
        return
    try:
        audit_log.record_stage(
            tenant_id=tenant_id,
            action_id=action_id,
            action_type=action_type,
            stage=stage,
            status=status,
            trace_id=trace_id,
            decision_id=str(getattr(decision, "decision_id", "") or "") or None,
            correlation_id=str(getattr(decision, "correlation_id", "") or "") or None,
            run_id=str(payload_map.get("run_id") or getattr(decision, "decision_id", "") or "") or None,
            payload=payload,
        )
    except Exception as exc:
        logger.warning("runtime_executor_action_audit_record_failed", exc_info=exc)




def record_inference_runtime_event(*, runtime_observability, env: DecisionEnvelope, stage: str, safe_dict) -> None:
    if runtime_observability is None:
        return
    method = getattr(runtime_observability, "record_execution_trace", None)
    if not callable(method):
        return
    decision = getattr(env, "decision", None)
    payload_map = safe_dict(getattr(decision, "payload", {}) or {})
    tenant_id = str(payload_map.get("tenant_id") or _decision_tenant_id(decision) or "").strip()
    provider_name = str(payload_map.get("inference_provider_name") or "").strip()
    capacity_tier = str(payload_map.get("inference_capacity_tier") or "").strip()
    if not tenant_id or not provider_name or not capacity_tier:
        return
    try:
        method(
            trace_name="inference_capacity",
            stage=str(stage),
            generated_at_ms=_generated_at_ms_from_env(env=env, safe_dict=safe_dict),
            tenant_id=tenant_id,
            provider_name=provider_name,
            capacity_tier=capacity_tier,
            verification_mode=str(payload_map.get("inference_verification_mode") or "").strip() or "standard",
        )
    except Exception as exc:
        logger.warning("runtime_executor_inference_runtime_trace_record_failed", exc_info=exc)

def record_connector_runtime_event(*, observability, env: DecisionEnvelope, status: str, payload: Mapping[str, Any] | None, safe_dict, runtime_observability=None) -> None:
    if observability is None or not hasattr(observability, "record"):
        return
    decision = getattr(env, "decision", None)
    decision_payload = safe_dict(getattr(decision, "payload", {}) or {})
    tenant_id = str(decision_payload.get("tenant_id") or _decision_tenant_id(decision) or "").strip()
    connector_id = str(decision_payload.get("connector_id") or decision_payload.get("provider_key") or "").strip()
    provider = str(decision_payload.get("connector_provider") or decision_payload.get("provider") or "runtime").strip()
    version = str(decision_payload.get("connector_version") or "unknown").strip()
    operation = str(getattr(decision, "action", "") or decision_payload.get("action_type") or "runtime.execute").strip()
    if not tenant_id or not connector_id:
        return
    try:
        observability.record(
            ConnectorExecutionEvent(
                tenant_id=tenant_id,
                connector_id=connector_id,
                provider=provider,
                version=version,
                operation=operation,
                status=status,
                trace_id=str(getattr(decision, "correlation_id", "") or "") or None,
                route_index=int((payload or {}).get("route_index", 0)),
                attempt=int((payload or {}).get("attempt", 0)),
                breaker_state=(payload or {}).get("breaker_state"),
                payload=dict(payload or {}),
            )
        )
    except Exception as exc:
        logger.warning("runtime_executor_connector_observability_record_failed", exc_info=exc)
    runtime_trace = getattr(runtime_observability, "record_effect_trace", None) if runtime_observability is not None else None
    if not callable(runtime_trace):
        return
    try:
        runtime_trace(
            trace_name="runtime_effect",
            stage=str(status),
            generated_at_ms=_generated_at_ms_from_env(env=env, safe_dict=safe_dict),
            tenant_id=tenant_id,
            connector_id=connector_id,
            provider=provider,
            operation=operation,
        )
    except Exception as exc:
        logger.warning("runtime_executor_effect_trace_append_failed", exc_info=exc)



def record_inference_budget_burn(*, budget_burn_log, env: DecisionEnvelope, safe_dict) -> None:
    if budget_burn_log is None or not hasattr(budget_burn_log, 'record'):
        return
    decision = getattr(env, 'decision', None)
    payload_map = safe_dict(getattr(decision, 'payload', {}) or {})
    tenant_id = str(payload_map.get('tenant_id') or _decision_tenant_id(decision) or '').strip()
    provider_name = str(payload_map.get('inference_provider_name') or '').strip()
    tier = str(payload_map.get('inference_capacity_tier') or '').strip()
    if not tenant_id or not provider_name or not tier:
        return
    try:
        budget_burn_log.record(
            tenant_id=tenant_id,
            provider_name=provider_name,
            tier=tier,
            estimated_cost_usd=float(payload_map.get('inference_estimated_cost_usd') or 0.0),
        )
    except Exception as exc:
        logger.warning('runtime_executor_inference_budget_burn_record_failed', exc_info=exc)
