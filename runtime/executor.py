"""RuntimeExecutor — единственный шлюз к необратимым эффектам.

Law (Decision Sovereignty):
  Any irreversible action is allowed ONLY via:
    RuntimeGuard.verify
    RuntimeGuard.execute_once
    RuntimeExecutor.execute

Security:
  - The private Effects implementation lives in runtime/_internal and MUST NOT be
    imported anywhere else (enforced by tests/test_architecture.py).
"""

from __future__ import annotations

# Historical entrypoint bundle markers retained for arch-locks:
# build_executor_entrypoint_bundle(
# entrypoint_bundle.run(executor=self, env=env)


import logging
import os
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from application.autonomy.autonomy_safety_bundle import AutonomySafetyBundle
from application.evidence.evidence_verifier import EvidenceVerifier
from execution.action_budget_engine import ActionBudgetEngine
from execution.blast_radius_guard import BlastRadiusGuard
from execution.bounded_autonomy import BoundedAutonomyGuard
from governance.constitution import Constitution
from governance.economic_layer import EconomicAutonomyLayer
from governance.time_scale import TimeScale
from observability.decision_trace_store import NullDecisionTraceStore
from runtime.decision import DecisionEnvelope
from runtime.enforcement.world_model_pin_guard import (
    enforce_world_model_pin_or_raise as _executor_world_model_pin_guard_contract,
)
from runtime.execution import executor_effect_delivery as _executor_effect_delivery
from runtime.execution.correlation import extract_correlation_key
from runtime.execution.executor_audit import emit_effect_window as _executor_audit_helper
from runtime.execution.executor_bindings import apply_executor_state
from runtime.execution.executor_commit import _decision_tenant_id, claim_or_skip, get_delivery_info
from runtime.execution.executor_core import enforce_safe_mode as _executor_core_helper
from runtime.execution.executor_observability import (
    append_decision_trace as append_executor_decision_trace,
)
from runtime.execution.executor_observability import (
    record_action_audit as record_executor_action_audit,
)
from runtime.execution.executor_observability import (
    record_connector_runtime_event as record_executor_connector_runtime_event,
)
from runtime.execution.executor_observability import (
    record_inference_budget_burn as record_executor_inference_budget_burn,
)
from runtime.execution.executor_observability import (
    record_inference_runtime_event as record_executor_inference_runtime_event,
)
from runtime.execution.executor_recovery import finalize_if_already_executed as _executor_recovery_helper
from runtime.execution.executor_reliability import apply_reliability_gate as executor_apply_reliability_gate
from runtime.execution.executor_result import ExecutionResult
from runtime.execution.executor_state import RuntimeExecutorInfra
from runtime.execution.executor_trace_runtime import (
    execute_with_trace as executor_execute_with_trace,
)
from runtime.execution.executor_trace_runtime import (
    trace_context_for_env as executor_trace_context_for_env,
)
from runtime.executor_api_support import (
    _deny_autonomy_execution as executor_api_deny_autonomy_execution,
)
from runtime.executor_api_support import (
    _dispatch as executor_api_dispatch,
)
from runtime.executor_api_support import (
    _enforce_runtime_budget_and_blast_radius as executor_api_enforce_runtime_budget_and_blast_radius,
)
from runtime.executor_api_support import (
    _ensure_tenant_runtime_contracts as executor_api_ensure_tenant_runtime_contracts,
)
from runtime.executor_api_support import (
    _tenant_runtime_context as executor_api_tenant_runtime_context,
)
from runtime.executor_api_support import (
    assert_called_from_executor,
    execute_core_flow,
    executor_context,
    preflight_and_verify,
)
from runtime.executor_api_support import (
    campaign_or_heartbeat_recovery_leader as executor_api_campaign_or_heartbeat_recovery_leader,
)
from runtime.executor_api_support import (
    campaign_or_heartbeat_scheduler_leader as executor_api_campaign_or_heartbeat_scheduler_leader,
)
from runtime.executor_api_support import (
    campaign_recovery_leader as executor_api_campaign_recovery_leader,
)
from runtime.executor_api_support import (
    campaign_scheduler_leader as executor_api_campaign_scheduler_leader,
)
from runtime.executor_api_support import (
    enqueue_runtime_job as executor_api_enqueue_runtime_job,
)
from runtime.executor_api_support import (
    run_queue_tick as executor_api_run_queue_tick,
)
from runtime.executor_api_support import (
    run_queue_tick_as_leader as executor_api_run_queue_tick_as_leader,
)
from runtime.executor_recovery_flow import execute_recovery_flow, has_proof_event
from runtime.executor_runtime_support import (
    build_executor_queue_support,
    build_executor_state,
    emit_throttled_executor_warning,
)
from runtime.handlers import ActionHandlerRegistry
from runtime.proofs import ACTION_PROOF_EVENT
from runtime.world_model import (
    extract_pinned_world_model_meta_from_payload as _executor_world_model_pin_extract_contract,
)
from tenancy.tenant_runtime_isolation import TenantRuntimeIsolation


from runtime._internal.economic_execution_contract import (
    SealedEconomicExecutionContract,
    build_click_provider_dispatch_execution_contract,
    build_spend_runtime_execution_contract,
)

CANON_RUNTIME_EXECUTION_GATEWAY = True
_EXECUTOR_SPLIT_HELPERS = (
    _executor_audit_helper,
    _executor_core_helper,
    _executor_recovery_helper,
    executor_apply_reliability_gate,
    executor_api_run_queue_tick,
    _executor_world_model_pin_extract_contract,
    _executor_world_model_pin_guard_contract,
)
logger = logging.getLogger(__name__)
_throttled_exec_warn = emit_throttled_executor_warning


class RuntimeExecutor:
    def __init__(
        self,
        guard,
        handlers: ActionHandlerRegistry,
        event_log,
        *,
        policy_registry,
        reward_engine=None,
        learning_system=None,
        decision_core=None,
        outbox=None,
        decision_archive=None,
        constitution: Constitution | None = None,
        max_meta_depth: int = 1,
        economic_layer: EconomicAutonomyLayer | None = None,
        snapshot_store=None,
        delivery_state=None,
        ledger=None,
        payment_outbox=None,
        telegram_outbound_queue=None,
        settings_gateway=None,
        messaging_policy_event_store=None,
        messaging_policy_read_service=None,
        runtime_infra: RuntimeExecutorInfra | None = None,
        operational_budget_service=None,
        queue_store=None,
        queue_dead_letter_store=None,
        queue_dispatcher=None,
        queue_scheduler=None,
        queue_worker=None,
        queue_runner=None,
        queue_rate_limit_guard=None,
        queue_backpressure_policy=None,
        queue_throttle_policy=None,
        queue_retry_policy=None,
        queue_worker_id: str = "runtime-executor",
        tenant_runtime_isolation: TenantRuntimeIsolation | None = None,
        tenant_execution_budget_guard: Any | None = None,
        action_audit_log: Any | None = None,
        execution_trace_store=None,
        decision_trace_store=None,
        runtime_effect_trace_store=None,
    ):
        state = build_executor_state(
            guard=guard,
            handlers=handlers,
            event_log=event_log,
            policy_registry=policy_registry,
            reward_engine=reward_engine,
            learning_system=learning_system,
            decision_core=decision_core,
            runtime_infra=runtime_infra,
            ledger=ledger,
            snapshot_store=snapshot_store,
            outbox=outbox,
            payment_outbox=payment_outbox,
            settings_gateway=settings_gateway,
            messaging_policy_event_store=messaging_policy_event_store,
            messaging_policy_read_service=messaging_policy_read_service,
            delivery_state=delivery_state,
            telegram_outbound_queue=telegram_outbound_queue,
            decision_archive=decision_archive,
            constitution=constitution,
            max_meta_depth=max_meta_depth,
            economic_layer=economic_layer,
        )
        apply_executor_state(executor=self, state=state)
        self._rebind_reliability_to_guard_ledger_if_needed()
        self._operational_budget_service = operational_budget_service
        self._governance_execution_guard = None
        self._action_budget_engine = ActionBudgetEngine()
        self._blast_radius_guard = BlastRadiusGuard(action_budget_engine=self._action_budget_engine)
        self._bounded_autonomy_guard = BoundedAutonomyGuard(action_budget_engine=self._action_budget_engine)
        self._autonomy_safety_bundle = AutonomySafetyBundle(action_budget_engine=self._action_budget_engine, blast_radius_guard=self._blast_radius_guard, bounded_autonomy_guard=self._bounded_autonomy_guard)
        self._tenant_runtime_isolation = tenant_runtime_isolation or getattr(runtime_infra, "tenant_runtime_isolation", None)
        self._tenant_execution_budget_guard = tenant_execution_budget_guard or getattr(runtime_infra, "tenant_execution_budget_guard", None)
        self._tenant_registry = getattr(runtime_infra, 'tenant_registry', None)
        self._runtime_observability = getattr(runtime_infra, 'runtime_observability', None)
        self._inference_budget_burn_log = getattr(runtime_infra, 'inference_budget_burn_log', None)
        self._runtime_owner_id = str(queue_worker_id or getattr(runtime_infra, 'runtime_owner_id', None) or 'runtime-executor').strip() or 'runtime-executor'
        self._action_audit_log = action_audit_log or getattr(runtime_infra, 'action_audit_log', None)
        self._execution_trace_store = execution_trace_store or getattr(runtime_infra, 'execution_trace_store', None)
        self._decision_trace_store = getattr(runtime_infra, 'decision_trace_store', None) or decision_trace_store or NullDecisionTraceStore()
        self._runtime_effect_trace_store = runtime_effect_trace_store or getattr(runtime_infra, 'runtime_effect_trace_store', None)
        self._connector_observability = getattr(runtime_infra, 'connector_observability', None)
        self._connector_health_monitor = getattr(runtime_infra, 'connector_health_monitor', None)
        self._connector_failover_router = getattr(runtime_infra, 'connector_failover_router', None)
        self._evidence_verifier = getattr(runtime_infra, 'evidence_verifier', None) or EvidenceVerifier()
        self._logger = logger
        self._queue_support = build_executor_queue_support(
            runtime_infra=runtime_infra,
            queue_store=queue_store,
            queue_dead_letter_store=queue_dead_letter_store,
            queue_dispatcher=queue_dispatcher,
            queue_scheduler=queue_scheduler,
            queue_worker=queue_worker,
            queue_runner=queue_runner,
            queue_rate_limit_guard=queue_rate_limit_guard,
            queue_backpressure_policy=queue_backpressure_policy,
            queue_throttle_policy=queue_throttle_policy,
            queue_retry_policy=queue_retry_policy,
            worker_id=str(queue_worker_id or "runtime-executor"),
        )

    def _rebind_reliability_to_guard_ledger_if_needed(self) -> None:
        runtime_infra = getattr(self, '_runtime_infra', None)
        reliability = getattr(self, '_reliability', None)
        guard = getattr(self, '_guard', None)
        guard_ledger = getattr(guard, '_ledger', None)
        ledger_path = str(getattr(guard_ledger, '_path', '') or '').strip()
        if runtime_infra is None or reliability is None or not ledger_path:
            return
        if str(os.getenv("DATA_DIR", "") or "").strip() or str(os.getenv("RUNTIME_DIR", "") or "").strip():
            return
        current_path = str(getattr(getattr(reliability, 'checkpoint_store', None), 'path', '') or '').strip()
        desired_base_dir = str(Path(ledger_path).parent / '.runtime')
        if current_path and current_path.startswith(desired_base_dir):
            return
        try:
            rebound_infra = replace(
                runtime_infra,
                ledger=guard_ledger,
                reliability_base_dir=desired_base_dir,
            )
            from runtime.execution.reliability_runtime import build_runtime_reliability
            self._runtime_infra = rebound_infra
            self._reliability = build_runtime_reliability(
                outbox=getattr(rebound_infra, 'effect_outbox', None),
                runtime_infra=rebound_infra,
            )
        except Exception as exc:
            logger.warning('runtime_executor_reliability_rebind_failed', exc_info=exc)

    def _trace_context_for_env(self, env: DecisionEnvelope):
        return executor_trace_context_for_env(env=env, safe_dict=self._safe_dict)

    def _append_decision_trace(self, env: DecisionEnvelope, trace_id: str | None) -> None:
        append_executor_decision_trace(
            store=getattr(self, '_decision_trace_store', None),
            env=env,
            trace_id=trace_id,
            safe_dict=self._safe_dict,
        )

    def _record_action_audit(self, *, env: DecisionEnvelope, trace_id: str | None, stage: str, status: str, payload: Mapping[str, Any] | None = None) -> None:
        record_executor_action_audit(
            audit_log=getattr(self, '_action_audit_log', None),
            env=env,
            trace_id=trace_id,
            stage=stage,
            status=status,
            payload=payload,
            safe_dict=self._safe_dict,
        )

    def _record_inference_selection_audit(self, *, env: DecisionEnvelope, trace_id: str | None) -> None:
        audit_log = getattr(self, '_action_audit_log', None)
        if audit_log is None or not hasattr(audit_log, 'record_inference_selection'):
            return
        decision = getattr(env, 'decision', None)
        payload_map = self._safe_dict(getattr(decision, 'payload', {}) or {})
        tenant_id = str(payload_map.get('tenant_id') or _decision_tenant_id(decision) or '').strip()
        action_id = str(payload_map.get('action_id') or getattr(decision, 'decision_id', '') or '').strip()
        action_type = str(getattr(decision, 'action', '') or payload_map.get('action_type') or '').strip()
        provider_name = str(payload_map.get('inference_provider_name') or '').strip()
        capacity_tier = str(payload_map.get('inference_capacity_tier') or '').strip()
        if not tenant_id or not action_id or not action_type or not provider_name or not capacity_tier:
            return
        try:
            audit_log.record_inference_selection(
                tenant_id=tenant_id,
                action_id=action_id,
                action_type=action_type,
                provider_name=provider_name,
                capacity_tier=capacity_tier,
                estimated_cost_usd=float(payload_map.get('inference_estimated_cost_usd') or 0.0),
                trace_id=trace_id,
                decision_id=str(getattr(decision, 'decision_id', '') or '') or None,
                correlation_id=str(getattr(decision, 'correlation_id', '') or '') or None,
                run_id=str(payload_map.get('run_id') or getattr(decision, 'decision_id', '') or '') or None,
                payload={
                    'inference_verification_mode': str(payload_map.get('inference_verification_mode') or '').strip() or None,
                },
            )
        except Exception as exc:
            logger.warning('runtime_executor_inference_selection_audit_record_failed', exc_info=exc)

    def _record_inference_verification_audit(self, *, env: DecisionEnvelope, trace_id: str | None) -> None:
        audit_log = getattr(self, '_action_audit_log', None)
        if audit_log is None or not hasattr(audit_log, 'record_inference_verification'):
            return
        decision = getattr(env, 'decision', None)
        payload_map = self._safe_dict(getattr(decision, 'payload', {}) or {})
        tenant_id = str(payload_map.get('tenant_id') or _decision_tenant_id(decision) or '').strip()
        action_id = str(payload_map.get('action_id') or getattr(decision, 'decision_id', '') or '').strip()
        action_type = str(getattr(decision, 'action', '') or payload_map.get('action_type') or '').strip()
        provider_name = str(payload_map.get('inference_provider_name') or '').strip()
        verification_reason = str(payload_map.get('inference_verification_reason') or '').strip()
        if not tenant_id or not action_id or not action_type or not provider_name or not verification_reason:
            return
        try:
            audit_log.record_inference_verification(
                tenant_id=tenant_id,
                action_id=action_id,
                action_type=action_type,
                provider_name=provider_name,
                accepted=str(payload_map.get('inference_verification_accepted') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
                verification_reason=verification_reason,
                trace_id=trace_id,
                decision_id=str(getattr(decision, 'decision_id', '') or '') or None,
                correlation_id=str(getattr(decision, 'correlation_id', '') or '') or None,
                run_id=str(payload_map.get('run_id') or getattr(decision, 'decision_id', '') or '') or None,
            )
        except Exception as exc:
            logger.warning('runtime_executor_inference_verification_audit_record_failed', exc_info=exc)

    def _record_connector_runtime_event(self, *, env: DecisionEnvelope, status: str, payload: Mapping[str, Any] | None = None) -> None:
        record_executor_connector_runtime_event(
            observability=getattr(self, '_connector_observability', None),
            env=env,
            status=status,
            payload=payload,
            safe_dict=self._safe_dict,
        )

    def _record_inference_runtime_trace(self, *, env: DecisionEnvelope, stage: str) -> None:
        record_executor_inference_runtime_event(
            runtime_observability=getattr(self, '_runtime_observability', None),
            env=env,
            stage=stage,
            safe_dict=self._safe_dict,
        )

    def execute(self, env: DecisionEnvelope) -> ExecutionResult:
        return executor_execute_with_trace(executor=self, env=env)

    def _extract_ck(self, snapshot_id: str):
        return extract_correlation_key(self._snapshot_store, str(snapshot_id))

    def _claim_or_skip_outbox(self, env: DecisionEnvelope) -> bool:
        claimed = claim_or_skip(
            self._outbox,
            decision_id=str(env.decision.decision_id),
            tenant_id=_decision_tenant_id(env.decision),
            owner_id="runtime-executor",
        )
        if not claimed:
            return False
        return True

    def _already_claimed_result(self, env: DecisionEnvelope) -> ExecutionResult:
        return ExecutionResult(
            ok=True,
            output={"status": "already_claimed"},
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
        )

    def _has_proof_event(self, *, decision_id: str, action: str) -> bool:
        expected_event = ACTION_PROOF_EVENT.get(str(action))
        if not expected_event or self._events is None or not hasattr(self._events, "has_event"):
            return False
        try:
            return bool(self._events.has_event(str(decision_id), expected_event))
        except Exception as exc:
            _throttled_exec_warn("has_proof_event", exc)
            return False

    def _mark_delivered_if_already_executed(self, env: DecisionEnvelope) -> ExecutionResult | None:
        return _executor_recovery_helper(
            executor=self,
            outbox=self._outbox,
            event_log=self._events,
            env=env,
        )

    def execute_recovery(self, env: DecisionEnvelope) -> ExecutionResult:
        return execute_recovery_flow(
            executor=self,
            env=env,
            outbox=self._outbox,
            guard=self._guard,
            event_log=self._events,
            executor_context_cm=executor_context,
            warn=_throttled_exec_warn,
        )

    def _execute(self, env: DecisionEnvelope, *, depth: int, timescale: TimeScale = TimeScale.RUNTIME) -> ExecutionResult:
        return execute_core_flow(executor=self, env=env, depth=depth, timescale=timescale)

    def _apply_reliability_gate(self, env: DecisionEnvelope) -> ExecutionResult | None:
        return executor_apply_reliability_gate(executor=self, env=env)


RuntimeExecutor._attach_effect_delivery_metadata = _executor_effect_delivery.attach_effect_delivery_metadata
RuntimeExecutor._safe_dict = staticmethod(_executor_effect_delivery.safe_dict)

RuntimeExecutor._ensure_tenant_runtime_contracts = executor_api_ensure_tenant_runtime_contracts
RuntimeExecutor._tenant_runtime_context = executor_api_tenant_runtime_context
RuntimeExecutor._deny_autonomy_execution = executor_api_deny_autonomy_execution
RuntimeExecutor._enforce_runtime_budget_and_blast_radius = executor_api_enforce_runtime_budget_and_blast_radius
RuntimeExecutor._dispatch = executor_api_dispatch
RuntimeExecutor.enqueue_runtime_job = executor_api_enqueue_runtime_job
RuntimeExecutor.run_queue_tick = executor_api_run_queue_tick
RuntimeExecutor.campaign_scheduler_leader = executor_api_campaign_scheduler_leader
RuntimeExecutor.campaign_or_heartbeat_scheduler_leader = executor_api_campaign_or_heartbeat_scheduler_leader
RuntimeExecutor.campaign_recovery_leader = executor_api_campaign_recovery_leader
RuntimeExecutor.campaign_or_heartbeat_recovery_leader = executor_api_campaign_or_heartbeat_recovery_leader
RuntimeExecutor.run_queue_tick_as_leader = executor_api_run_queue_tick_as_leader

__all__ = ['CANON_RUNTIME_EXECUTION_GATEWAY', 'RuntimeExecutor', 'assert_called_from_executor', 'executor_context', 'preflight_and_verify', 'execute_core_flow']

# Canonical public gateway for economic sealed execution contracts.
# The implementation stays runtime-internal; entrypoints import only from this
# executor surface to preserve one guarded execution contract and prevent
# route-level provider dispatch logic from becoming a second execution brain.
