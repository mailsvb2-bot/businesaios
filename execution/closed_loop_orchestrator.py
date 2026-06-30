from __future__ import annotations

from execution.economic_scope_lineage import EconomicScopeLineageGuard
from execution.economic_state_monotonicity import EconomicStateMonotonicityGuard
from execution.economic_lineage_lock import EconomicLineageLockBuilder
from execution.economic_bundle_immutability import EconomicBundleImmutabilityValidator
from execution.economic_semantic_validation import EconomicSemanticValidator
from execution.economic_segment_validation import EconomicSegmentValidator
from execution.economic_schema_validation import EconomicSchemaValidator
from execution.economic_replay_epoch_guard import EconomicReplayEpochGuard
from execution.economic_schema_migration_matrix import EconomicSchemaMigrationMatrix

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping
from pathlib import Path

from execution.action_verification_policy import ActionVerificationPolicy, build_action_verification_policy
from execution.autonomy_policy import AutonomyPolicy, autonomy_input_from_world_state
from application.evidence.evidence_persistence import EvidencePersistenceService, apply_feedback_to_world_state
from application.evidence.evidence_verifier import EvidenceVerifier
from execution.opportunity_detector import OpportunityDetector
from execution.outcome_verifier import OutcomeExpectation, expectation_from_action
from execution.world_state_updater import WorldStateUpdater
from execution.economic_memory_feedback import EconomicMemoryFeedback
from execution.cross_run_economic_audit import CrossRunEconomicAuditBuilder
from execution.economic_store_wiring import EconomicStoreWiring
from execution.economic_audit_bundle import EconomicAuditBundleService
from compliance.economic_forensics_service import EconomicForensicsService
from execution.economic_recovery_handoff import EconomicRecoveryHandoffBuilder
from execution.economic_policy_snapshot import EconomicPolicySnapshotBuilder
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_retention_policy import EconomicRetentionPolicy
from execution.economic_memory_store import EconomicMemoryStore, NoOpEconomicMemoryStore
from execution.economic_scope_profile import EconomicScopeProfileResolver
from execution.replay_safe_roi_history import ROIHistoryStore, NoOpROIHistoryStore, ReplaySafeROIHistoryBuilder
from execution.capital_rebalancer import CapitalRebalancer
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_queue_scope import TenantQueueScope
from observability.action_audit_log import ActionAuditLog
from observability.economic_trace_store import EconomicTraceStore, NoOpEconomicTraceStore
from observability.economic_metrics_stream import EconomicMetricsSink, NoOpEconomicMetricsStream
from observability.economic_metrics_store import EconomicMetricsStore, NoOpEconomicMetricsStore
from observability.economic_policy_snapshot_store import EconomicPolicySnapshotStore, NoOpEconomicPolicySnapshotStore
from observability.execution_span import execution_span
from observability.execution_trace_contract import TraceStage
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

CANON_CLOSED_LOOP_ORCHESTRATOR = True


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


@dataclass(frozen=True, slots=True)
class ClosedLoopCycleInput:
    action: dict[str, Any]
    world_state: Any | None = None
    execution_receipt: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)
    router_evidence: dict[str, Any] = field(default_factory=dict)
    requested_tier: str = 'supervised'
    current_tier: str = 'supervised'
    approval_required: bool = False
    budget_allowed: bool = True
    blast_radius_allowed: bool = True
    approval_context: dict[str, Any] = field(default_factory=dict)
    capability_context: dict[str, Any] = field(default_factory=dict)
    replanning_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClosedLoopCycleResult:
    verification_result: dict[str, Any]
    world_state_update: dict[str, Any]
    persisted_memory_evidence: dict[str, Any]
    next_tier_context: dict[str, Any]
    opportunity_signals: tuple[dict[str, Any], ...]
    world_state: Any
    verification_policy: dict[str, Any] = field(default_factory=dict)
    reliability_trace: dict[str, Any] = field(default_factory=dict)
    capability_context: dict[str, Any] = field(default_factory=dict)
    replanning_context: dict[str, Any] = field(default_factory=dict)


class ClosedLoopOrchestrator:
    def __init__(self, *, evidence_verifier: EvidenceVerifier | None = None, world_state_updater: WorldStateUpdater | None = None, evidence_persistence_service: EvidencePersistenceService | None = None, autonomy_policy: AutonomyPolicy | None = None, opportunity_detector: OpportunityDetector | None = None, tenant_execution_budget_guard: TenantExecutionBudgetGuard | None = None, tenant_registry: object | None = None, event_log: object | None = None, execution_trace_store: object | None = None, action_audit_log: ActionAuditLog | None = None, economic_trace_store: EconomicTraceStore | None = None, economic_metrics_stream: EconomicMetricsSink | None = None, economic_metrics_store: EconomicMetricsStore | None = None, economic_policy_snapshot_store: EconomicPolicySnapshotStore | None = None, economic_memory_store: EconomicMemoryStore | None = None, roi_history_store: ROIHistoryStore | None = None, economic_storage_root: str | Path | None = None) -> None:
        self._evidence_verifier = evidence_verifier or EvidenceVerifier()
        self._world_state_updater = world_state_updater or WorldStateUpdater()
        self._evidence_persistence_service = evidence_persistence_service or EvidencePersistenceService()
        self._autonomy_policy = autonomy_policy or AutonomyPolicy()
        self._opportunity_detector = opportunity_detector or OpportunityDetector()
        self._tenant_execution_budget_guard = tenant_execution_budget_guard
        self._tenant_registry = tenant_registry
        self._event_log = event_log
        self._execution_trace_store = execution_trace_store
        self._action_audit_log = action_audit_log
        self._economic_memory_feedback = EconomicMemoryFeedback()
        self._capital_rebalancer = CapitalRebalancer()
        self._policy_snapshot_builder = EconomicPolicySnapshotBuilder()
        self._cross_run_economic_audit = CrossRunEconomicAuditBuilder()
        self._economic_multi_backend_reconciliation = EconomicMultiBackendReconciliationBuilder()
        self._economic_recovery_handoff = EconomicRecoveryHandoffBuilder()
        store_bundle = EconomicStoreWiring(root_dir=economic_storage_root).build() if economic_storage_root is not None else None
        self._economic_store_bundle = store_bundle
        self._economic_forensics_service = EconomicForensicsService(
            store=(store_bundle.forensics_store if store_bundle is not None else None)
        )
        self._economic_audit_bundle_service = EconomicAuditBundleService(
            quarantine_sink=(store_bundle.quarantine_store if store_bundle is not None else None),
            forensics_service=self._economic_forensics_service,
        )
        self._economic_scope_profile_resolver = EconomicScopeProfileResolver(base_retention_policy=(store_bundle.retention_policy if store_bundle is not None else None))
        self._economic_retention_policy = EconomicRetentionPolicy.from_mapping(store_bundle.retention_policy if store_bundle is not None else None)
        self._economic_trace_store = economic_trace_store if economic_trace_store is not None else (store_bundle.trace_store if store_bundle is not None else NoOpEconomicTraceStore())
        self._economic_metrics_stream = economic_metrics_stream if economic_metrics_stream is not None else NoOpEconomicMetricsStream()
        self._economic_metrics_store = economic_metrics_store if economic_metrics_store is not None else (store_bundle.metrics_store if store_bundle is not None else NoOpEconomicMetricsStore())
        self._economic_policy_snapshot_store = economic_policy_snapshot_store if economic_policy_snapshot_store is not None else (store_bundle.policy_snapshot_store if store_bundle is not None else NoOpEconomicPolicySnapshotStore())
        self._economic_memory_store = economic_memory_store if economic_memory_store is not None else (store_bundle.memory_store if store_bundle is not None else NoOpEconomicMemoryStore())
        self._roi_history_builder = ReplaySafeROIHistoryBuilder()
        self._roi_history_store = roi_history_store if roi_history_store is not None else (store_bundle.roi_history_store if store_bundle is not None else NoOpROIHistoryStore())

    def _observability_scope(self, *, action: Mapping[str, Any], execution_receipt: Mapping[str, Any]):
        tenant_id = str(action.get('tenant_id') or execution_receipt.get('tenant_id') or '').strip()
        run_id = str(action.get('run_id') or action.get('decision_id') or execution_receipt.get('decision_id') or action.get('action_id') or '').strip()
        if not tenant_id or not run_id:
            return nullcontext()
        return execution_span(
            stage=TraceStage.VERIFICATION,
            tenant_id=tenant_id,
            run_id=run_id,
            event_log=self._event_log,
            execution_trace_store=self._execution_trace_store,
            decision_id=str(action.get('decision_id') or execution_receipt.get('decision_id') or '') or None,
            correlation_id=str(action.get('correlation_id') or execution_receipt.get('correlation_id') or '') or None,
            action_id=str(action.get('action_id') or '') or None,
            executor_name='ClosedLoopOrchestrator',
            component='execution.closed_loop_orchestrator',
            success_payload={'phase': 'closed_loop_cycle'},
            failure_payload_builder=lambda exc: {'error': type(exc).__name__, 'message': str(exc)},
        )

    def _record_cycle_audit(self, *, action: Mapping[str, Any], execution_receipt: Mapping[str, Any], status: str, payload: Mapping[str, Any] | None = None) -> None:
        audit_log = getattr(self, '_action_audit_log', None)
        if audit_log is None or not hasattr(audit_log, 'record_stage'):
            return
        tenant_id = str(action.get('tenant_id') or execution_receipt.get('tenant_id') or '').strip()
        action_id = str(action.get('action_id') or action.get('decision_id') or execution_receipt.get('decision_id') or '').strip()
        action_type = str(action.get('action_type') or '').strip()
        if not tenant_id or not action_id or not action_type:
            return
        audit_log.record_stage(
            tenant_id=tenant_id,
            action_id=action_id,
            action_type=action_type,
            stage='closed_loop.run_cycle',
            status=status,
            trace_id=str(action.get('trace_id') or execution_receipt.get('trace_id') or action.get('correlation_id') or execution_receipt.get('correlation_id') or '') or None,
            decision_id=str(action.get('decision_id') or execution_receipt.get('decision_id') or '') or None,
            correlation_id=str(action.get('correlation_id') or execution_receipt.get('correlation_id') or '') or None,
            run_id=str(action.get('run_id') or action.get('decision_id') or action_id) or None,
            payload=payload,
        )

    def run_cycle(self, *, cycle_input: ClosedLoopCycleInput, expectation: OutcomeExpectation | None = None) -> ClosedLoopCycleResult:
        action = _safe_dict(cycle_input.action)
        execution_receipt = _safe_dict(cycle_input.execution_receipt)
        self._record_cycle_audit(action=action, execution_receipt=execution_receipt, status='started')
        try:
            with self._observability_scope(action=action, execution_receipt=execution_receipt):
                self._assert_tenant_consistency(action=action, execution_receipt=execution_receipt)
                approval_context = _normalize_approval_context(action=action, execution_receipt=execution_receipt, approval_context=cycle_input.approval_context)
                tenant_scope = self._tenant_scope_for(action=action, execution_receipt=execution_receipt)
                budget_verdict = self._resolve_tenant_budget(action=action, execution_receipt=execution_receipt)
                policy: ActionVerificationPolicy = build_action_verification_policy(action, default_mode='required')
                verification = self._evidence_verifier.verify(
                    action=action,
                    execution_receipt=execution_receipt,
                    feedback=cycle_input.feedback,
                    router_evidence=cycle_input.router_evidence,
                    expectation=expectation or expectation_from_action(action.get('action_type', ''), external_confirmation_mode=policy.external_confirmation_mode),
                ).to_dict()
                update = self._world_state_updater.build_update(verification_result=verification, action=action)
                state = self._world_state_updater.apply(world_state=cycle_input.world_state, update=update)
                persisted = self._evidence_persistence_service.build_feedback_artifacts(verification_result=verification)
                reliability_trace = _stable_reliability_trace(action=action, verification=verification, execution_receipt=execution_receipt)
                recovery_summary = _build_recovery_summary(execution_receipt=execution_receipt, reliability_trace=reliability_trace)
                receipt_payload = {**_safe_dict(persisted.get('persistence_receipt')), 'reliability_trace': reliability_trace}
                if tenant_scope is not None:
                    receipt_payload['tenant_scope'] = {
                        'tenant_id': tenant_scope.tenant_id,
                        'queue_name': tenant_scope.queue_name,
                        'namespace': tenant_scope.namespace,
                        'scope_key': tenant_scope.scope_key,
                    }
                if budget_verdict is not None:
                    receipt_payload['tenant_budget'] = self._budget_verdict_dict(budget_verdict)
                if recovery_summary:
                    receipt_payload['recovery'] = recovery_summary
                state = apply_feedback_to_world_state(world_state=state, verification_result=verification, receipt=receipt_payload)
                mapping = state if isinstance(state, Mapping) else {'meta': getattr(state, 'meta', {})}
                decision_agi_payload = _extract_decision_agi_payload(state)
                compact_decision_agi = _compact_decision_agi_payload(decision_agi_payload)
                next_tier = self._autonomy_policy.evaluate(
                    autonomy_input_from_world_state(
                        mapping,
                        requested_tier=cycle_input.requested_tier,
                        current_tier=cycle_input.current_tier,
                        approval_required=cycle_input.approval_required or bool(approval_context.get('approval_required', False)),
                        budget_allowed=cycle_input.budget_allowed and (budget_verdict.allowed if budget_verdict is not None else True),
                        blast_radius_allowed=cycle_input.blast_radius_allowed,
                    )
                ).to_dict()
                if approval_context:
                    next_tier = {
                        **next_tier,
                        'approval_required': bool(approval_context.get('approval_required', next_tier.get('approval_required', False))),
                        'operator_required': bool(approval_context.get('operator_required', False) or next_tier.get('operator_required', False)),
                    }
                persistence_receipt = _safe_dict(persisted.get('persistence_receipt'))
                capability_context = _safe_dict(cycle_input.capability_context)
                replanning_context = _safe_dict(cycle_input.replanning_context)
                inference_runtime = _extract_inference_runtime_context(action=action, execution_receipt=execution_receipt)
                persisted_payload = {**dict(persisted), 'reliability_trace': reliability_trace, 'idempotency_scope': reliability_trace.get('semantic_scope', {})}
                if tenant_scope is not None:
                    persisted_payload['tenant_scope'] = {
                        'tenant_id': tenant_scope.tenant_id,
                        'queue_name': tenant_scope.queue_name,
                        'namespace': tenant_scope.namespace,
                        'scope_key': tenant_scope.scope_key,
                    }
                if budget_verdict is not None:
                    persisted_payload['tenant_budget'] = self._budget_verdict_dict(budget_verdict)
                if recovery_summary:
                    persisted_payload['recovery'] = recovery_summary
                if approval_context:
                    persisted_payload['approval'] = approval_context
                if inference_runtime:
                    persisted_payload['inference_runtime'] = inference_runtime
                if capability_context:
                    persisted_payload['capability'] = capability_context
                if replanning_context:
                    persisted_payload['capability_replanning'] = replanning_context
                if persistence_receipt:
                    persisted_payload['effect_delivery'] = {
                        'effect_key': persistence_receipt.get('effect_key'),
                        'outbox_message_id': persistence_receipt.get('outbox_message_id'),
                        'outbox_state': persistence_receipt.get('outbox_state'),
                        'outbox_topic': persistence_receipt.get('outbox_topic'),
                        'outbox_backend_name': persistence_receipt.get('outbox_backend_name'),
                        'outbox_external_id': persistence_receipt.get('outbox_external_id'),
                        'outbox_delivered_at': persistence_receipt.get('outbox_delivered_at'),
                        'delivery_guarantee': persistence_receipt.get('delivery_guarantee'),
                        'runtime_effect_delivery': _safe_dict(persistence_receipt.get('runtime_effect_delivery')),
                        'outbox_delivery_metadata': _safe_dict(persistence_receipt.get('outbox_delivery_metadata')),
                    }
                if compact_decision_agi.get('selected_goal') or compact_decision_agi.get('strategy_hints'):
                    persisted_payload['decision_agi'] = compact_decision_agi
                next_tier = {**next_tier, 'closed_loop_trace_key': reliability_trace['trace_key'], 'idempotency_scope': reliability_trace.get('semantic_scope', {})}
                if tenant_scope is not None:
                    next_tier['tenant_scope'] = {
                        'tenant_id': tenant_scope.tenant_id,
                        'queue_name': tenant_scope.queue_name,
                        'namespace': tenant_scope.namespace,
                        'scope_key': tenant_scope.scope_key,
                    }
                if budget_verdict is not None:
                    next_tier['tenant_budget'] = self._budget_verdict_dict(budget_verdict)
                if recovery_summary:
                    next_tier['recovery'] = recovery_summary
                if approval_context:
                    next_tier['approval'] = approval_context
                    handoff = _build_approval_handoff(action=action, approval_context=approval_context, next_tier=next_tier)
                    if handoff:
                        next_tier['operator_handoff'] = handoff
                if inference_runtime:
                    next_tier['inference_runtime'] = inference_runtime
                if capability_context:
                    next_tier['capability'] = capability_context
                if replanning_context:
                    next_tier['capability_replanning'] = replanning_context
                if persistence_receipt:
                    next_tier['effect_delivery'] = {
                        'effect_key': persistence_receipt.get('effect_key'),
                        'outbox_state': persistence_receipt.get('outbox_state'),
                        'outbox_backend_name': persistence_receipt.get('outbox_backend_name'),
                        'delivery_guarantee': persistence_receipt.get('delivery_guarantee'),
                        'runtime_effect_delivery': _safe_dict(persistence_receipt.get('runtime_effect_delivery')),
                        'outbox_delivery_metadata': _safe_dict(persistence_receipt.get('outbox_delivery_metadata')),
                    }
                if compact_decision_agi.get('selected_goal') or compact_decision_agi.get('strategy_hints'):
                    next_tier['decision_agi'] = compact_decision_agi
                raw_signals = [signal.to_dict() for signal in self._opportunity_detector.detect(mapping)]
                agi_signals = _safe_list(decision_agi_payload.get('opportunity_signals'))
                for agi_signal in agi_signals:
                    signal_dict = _safe_dict(agi_signal)
                    if signal_dict:
                        raw_signals.append(signal_dict)
                deduped_signals: list[dict[str, Any]] = []
                seen_signal_keys: set[tuple[str, str, str]] = set()
                for item in raw_signals:
                    signal_key = (
                        str(item.get('signal_type') or ''),
                        str(item.get('title') or ''),
                        str(item.get('rationale') or ''),
                    )
                    if signal_key in seen_signal_keys:
                        continue
                    seen_signal_keys.add(signal_key)
                    deduped_signals.append({
                        **item,
                        'trace_key': reliability_trace['trace_key'],
                        'decision_agi_signal': item in agi_signals,
                    })
                    if len(deduped_signals) >= 16:
                        break
                signals = tuple(deduped_signals)
                budget_guard_result, revenue_verification_result = self._extract_economic_payload(
                    action=action,
                    execution_receipt=execution_receipt,
                    verification=verification,
                    persisted_payload=persisted_payload,
                )
                planning_signals = _safe_dict(_safe_dict(budget_guard_result).get('metadata')).get('planning_signals') or {}
                economic_event_id = _economic_event_id(action=action, persisted_payload=persisted_payload, reliability_trace=reliability_trace)
                economic_scope_profile = self._economic_scope_profile_resolver.resolve(
                    action=action,
                    execution_receipt=execution_receipt,
                    economic_policy=_safe_dict(_safe_dict(budget_guard_result).get('economic_policy')),
                )
                economic_retention_policy = EconomicRetentionPolicy.from_mapping(economic_scope_profile.retention_policy)
                economic_feedback = self._economic_memory_feedback.build(
                    action_type=str(action.get('action_type') or ''),
                    event_id=economic_event_id,
                    budget_guard_result=budget_guard_result,
                    planning_signals=planning_signals,
                    revenue_verification_result=revenue_verification_result,
                )
                economic_trace = self._economic_trace_store.append_from_results(
                    trace_id=str(action.get('action_id') or action.get('decision_id') or ''),
                    action_type=str(action.get('action_type') or ''),
                    budget_guard_result=budget_guard_result,
                    revenue_verification_result=revenue_verification_result,
                    planning_signals=planning_signals,
                )
                self._economic_metrics_stream.record_budget_guard(budget_guard_result)
                self._economic_metrics_stream.record_revenue_verification(revenue_verification_result)
                snapshot = self._policy_snapshot_builder.build(
                    snapshot_id=str(action.get("action_id") or action.get("decision_id") or reliability_trace.get("trace_key") or ""),
                    budget_guard_result=budget_guard_result,
                )
                stored_snapshot = self._economic_policy_snapshot_store.append_payload(snapshot.to_dict())
                stored_economic_feedback = self._economic_memory_store.upsert_payload(economic_feedback.to_memory_fact())
                stored_roi_history = self._roi_history_store.upsert(
                    self._roi_history_builder.build(
                        event_id=economic_event_id,
                        economic_feedback=stored_economic_feedback.to_dict(),
                        policy_snapshot=stored_snapshot.to_dict(),
                    )
                )
                state = _apply_economic_history_to_state(
                    world_state=state,
                    economic_feedback=stored_economic_feedback.to_dict(),
                    roi_history=stored_roi_history.to_dict(),
                    policy_snapshot=stored_snapshot.to_dict(),
                )
                portfolio_signals = _safe_dict(_safe_dict(persisted_payload.get('meta')).get('portfolio_roi_signals'))
                current_allocations = _safe_dict(_safe_dict(persisted_payload.get('meta')).get('current_capital_allocations'))
                rebalance_plan = self._capital_rebalancer.build_plan(
                    portfolio_signals=portfolio_signals,
                    current_allocations=current_allocations,
                )
                metrics_snapshot = {
                    'snapshot_id': economic_event_id,
                    'counters': self._economic_metrics_stream.snapshot(),
                    'metadata': {'owner': 'execution.closed_loop_orchestrator', 'trace_key': reliability_trace.get('trace_key')},
                }
                stored_metrics_snapshot = self._economic_metrics_store.upsert_payload(metrics_snapshot)
                economic_cross_run_audit = self._build_cross_run_economic_audit()
                economic_audit_bundle = self._build_economic_audit_bundle(bundle_id=economic_event_id, audit_summary=economic_cross_run_audit)
                economic_audit_bundle_entry = self._write_economic_audit_bundle(bundle_name=economic_event_id, bundle=economic_audit_bundle)
                economic_export_manifest = self._economic_audit_bundle_service.build_export_manifest(
                    stores=self._economic_store_mapping(),
                    bundle_path=economic_audit_bundle_entry.get('path') or None,
                    retention=economic_retention_policy.to_dict(),
                    scope=economic_scope_profile.to_dict(),
                    node_id=(self._economic_store_bundle.node_id if self._economic_store_bundle is not None else 'local-primary'),
                )
                economic_bundle_reconciliation = self._build_economic_bundle_reconciliation(bundle=economic_audit_bundle, bundle_entry=economic_audit_bundle_entry)
                economic_recovery_handoff = self._economic_recovery_handoff.build(
                    run_id=str(action.get('run_id') or action.get('decision_id') or action.get('action_id') or ''),
                    recovery_summary=recovery_summary,
                    audit_summary=economic_cross_run_audit,
                    bundle_id=str(economic_audit_bundle.get('bundle_id') or economic_event_id),
                )
                persisted_payload['economic_feedback'] = stored_economic_feedback.to_dict()
                persisted_payload['economic_event_id'] = economic_event_id
                persisted_payload['economic_trace'] = economic_trace.to_dict()
                persisted_payload['economic_policy_snapshot'] = stored_snapshot.to_dict()
                persisted_payload['economic_roi_history'] = stored_roi_history.to_dict()
                persisted_payload['economic_metrics_snapshot'] = stored_metrics_snapshot.to_dict()
                persisted_payload['economic_cross_run_audit'] = economic_cross_run_audit
                persisted_payload['economic_audit_bundle'] = economic_audit_bundle
                persisted_payload['economic_audit_bundle_entry'] = economic_audit_bundle_entry
                persisted_payload['economic_export_manifest'] = economic_export_manifest
                persisted_payload['economic_scope_profile'] = economic_scope_profile.to_dict()
                persisted_payload['economic_bundle_reconciliation'] = economic_bundle_reconciliation
                if economic_recovery_handoff is not None:
                    persisted_payload['economic_recovery_handoff'] = economic_recovery_handoff.to_dict()
                persisted_payload['capital_rebalance_plan'] = rebalance_plan.to_dict()
                if isinstance(state, Mapping):
                    meta = _safe_dict(state.get('meta'))
                    meta['economic_cross_run_audit'] = dict(persisted_payload['economic_cross_run_audit'])
                    meta['economic_audit_bundle'] = dict(persisted_payload['economic_audit_bundle'])
                    meta['economic_audit_bundle_entry'] = dict(persisted_payload['economic_audit_bundle_entry'])
                    meta['economic_export_manifest'] = dict(persisted_payload['economic_export_manifest'])
                    meta['economic_scope_profile'] = dict(persisted_payload['economic_scope_profile'])
                    meta['economic_bundle_reconciliation'] = dict(persisted_payload['economic_bundle_reconciliation'])
                    if 'economic_recovery_handoff' in persisted_payload:
                        meta['economic_recovery_handoff'] = dict(persisted_payload['economic_recovery_handoff'])
                    state = {**state, 'meta': meta}
                elif hasattr(state, 'meta'):
                    meta = _safe_dict(getattr(state, 'meta', {}))
                    meta['economic_cross_run_audit'] = dict(persisted_payload['economic_cross_run_audit'])
                    meta['economic_audit_bundle'] = dict(persisted_payload['economic_audit_bundle'])
                    meta['economic_audit_bundle_entry'] = dict(persisted_payload['economic_audit_bundle_entry'])
                    meta['economic_export_manifest'] = dict(persisted_payload['economic_export_manifest'])
                    meta['economic_scope_profile'] = dict(persisted_payload['economic_scope_profile'])
                    meta['economic_bundle_reconciliation'] = dict(persisted_payload['economic_bundle_reconciliation'])
                    if 'economic_recovery_handoff' in persisted_payload:
                        meta['economic_recovery_handoff'] = dict(persisted_payload['economic_recovery_handoff'])
                    object.__setattr__(state, 'meta', meta)
                result = ClosedLoopCycleResult(
                    verification_result=verification,
                    world_state_update=update.to_dict(),
                    persisted_memory_evidence=persisted_payload,
                    next_tier_context=next_tier,
                    opportunity_signals=signals,
                    world_state=state,
                    verification_policy=policy.to_dict(),
                    reliability_trace=reliability_trace,
                    capability_context=capability_context,
                    replanning_context=replanning_context,
                )
                self._record_cycle_audit(
                    action=action,
                    execution_receipt=execution_receipt,
                    status='succeeded',
                    payload={
                        'verification_status': verification.get('verification_status') or _safe_dict(verification.get('verification')).get('status'),
                        'inference_capacity_tier': inference_runtime.get('capacity_tier') if inference_runtime else None,
                        'inference_provider_name': inference_runtime.get('provider_name') if inference_runtime else None,
                    },
                )
                return result
        except Exception as exc:
            self._record_cycle_audit(
                action=action,
                execution_receipt=execution_receipt,
                status='failed',
                payload={'error': type(exc).__name__, 'message': str(exc)},
            )
            raise

    def _economic_store_mapping(self) -> dict[str, object]:
        return {
            'memory_store': self._economic_memory_store,
            'roi_history_store': self._roi_history_store,
            'policy_snapshot_store': self._economic_policy_snapshot_store,
            'trace_store': self._economic_trace_store,
            'metrics_store': self._economic_metrics_store,
        }

    def _build_economic_audit_bundle(self, *, bundle_id: str, audit_summary: Mapping[str, Any] | None = None, scope_profile: Mapping[str, Any] | None = None, retention_policy: EconomicRetentionPolicy | None = None) -> dict[str, Any]:
        bundle = self._economic_audit_bundle_service.build_bundle(
            bundle_id=bundle_id,
            feedback_rows=[row.to_dict() for row in self._economic_memory_store.list_rows()],
            roi_rows=[row.to_dict() for row in self._roi_history_store.list_rows()],
            snapshot_rows=[row.to_dict() for row in self._economic_policy_snapshot_store.list_rows()],
            trace_rows=[row.to_dict() for row in self._economic_trace_store.list_rows()],
            metrics_rows=[row.to_dict() for row in self._economic_metrics_store.list_rows()],
            audit_summary=audit_summary,
            export_manifest=self._economic_audit_bundle_service.build_export_manifest(
                stores=self._economic_store_mapping(),
                retention=(retention_policy or self._economic_retention_policy).to_dict(),
                node_id=(self._economic_store_bundle.node_id if self._economic_store_bundle is not None else 'local-primary'),
                scope=scope_profile,
                scope_lineage={'old_scope': dict(scope_profile or {}), 'new_scope': dict(scope_profile or {})},
            ),
            retention_policy=(retention_policy or self._economic_retention_policy),
            scope_profile=scope_profile,
        )
        return bundle.to_dict()

    def _write_economic_audit_bundle(self, *, bundle_name: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
        if self._economic_store_bundle is None:
            return {'bundle_kind': 'economic', 'bundle_name': str(bundle_name), 'path': ''}
        from execution.economic_audit_bundle import EconomicAuditBundle
        bundle_obj = EconomicAuditBundle(
            bundle_id=str(bundle.get('bundle_id') or bundle_name),
            payload=_safe_dict(bundle.get('payload')),
            digest=str(bundle.get('digest') or ''),
        )
        return self._economic_audit_bundle_service.write_bundle(
            bundle=bundle_obj,
            root_dir=self._economic_store_bundle.root_dir,
            bundle_name=bundle_name,
            catalog_path=self._economic_store_bundle.bundle_catalog_path,
        )

    def _build_economic_bundle_reconciliation(self, *, bundle: Mapping[str, Any], bundle_entry: Mapping[str, Any] | None = None) -> dict[str, Any]:
        bundle_payloads = [bundle]
        entry = _safe_dict(bundle_entry)
        bundle_path = str(entry.get('path') or '').strip()
        expected_scope = _safe_dict(_safe_dict(_safe_dict(bundle).get('payload')).get('export_manifest')).get('scope') if _safe_dict(bundle).get('payload') else _safe_dict(_safe_dict(bundle).get('export_manifest')).get('scope')
        expected_profile_name = str(_safe_dict(expected_scope).get('profile_name') or '').strip() or None
        import_validation = {
            'valid': True,
            'issues': [],
            'source': 'in_memory_bundle',
        }
        if bundle_path:
            try:
                restored_bundle = self._economic_audit_bundle_service.restore_bundle(
                    bundle_path=bundle_path,
                    strict_validation=True,
                    expected_scope=_safe_dict(expected_scope),
                    expected_profile_name=expected_profile_name,
                    require_bundle_segment=False,
                )
                restored_payload = _safe_dict(restored_bundle.get('payload')) or _safe_dict(restored_bundle)
                schema_verdict = EconomicSchemaValidator().validate(payload=restored_payload)
                migration_verdict = EconomicSchemaMigrationMatrix().validate(bundle_payload=restored_payload)
                segment_verdict = EconomicSegmentValidator().validate(payload=restored_payload)
                semantic_verdict = EconomicSemanticValidator().validate(payload=restored_payload)
                scope_lineage_verdict = EconomicScopeLineageGuard().validate(
                    current_scope=_safe_dict(expected_scope),
                    incoming_scope=_safe_dict(_safe_dict(restored_payload.get('export_manifest')).get('scope')),
                    declared_lineage=_safe_dict(_safe_dict(restored_payload.get('export_manifest')).get('scope_lineage')),
                )
                replay_epoch_verdict = EconomicReplayEpochGuard().validate(
                    current_state={},
                    incoming_payload=restored_payload,
                )
                monotonicity_verdict = EconomicStateMonotonicityGuard().validate(
                    current_state={},
                    incoming_payload=restored_payload,
                )
                lineage_lock_verdict = EconomicLineageLockBuilder().validate(
                    manifest=_safe_dict(restored_payload.get('export_manifest')),
                    expected_scope=_safe_dict(expected_scope),
                )
                immutability_verdict = EconomicBundleImmutabilityValidator().validate(bundle=restored_bundle)
                if not migration_verdict.supported:
                    raise ValueError(migration_verdict.reason)
                if not monotonicity_verdict.valid:
                    raise ValueError(monotonicity_verdict.reason)
                if not lineage_lock_verdict.valid:
                    raise ValueError(lineage_lock_verdict.reason)
                if not immutability_verdict.valid:
                    raise ValueError(immutability_verdict.reason)
                bundle_payloads = [restored_bundle]
                import_validation = {
                    'valid': True,
                    'issues': [],
                    'source': 'bundle_restore',
                    'status': 'valid',
                    'schema': schema_verdict.to_dict(),
                    'migration': migration_verdict.to_dict(),
                    'segments': segment_verdict.to_dict(),
                    'semantic': semantic_verdict.to_dict(),
                    'scope_lineage': scope_lineage_verdict.to_dict(),
                    'replay_epoch': replay_epoch_verdict.to_dict(),
                    'state_monotonicity': monotonicity_verdict.to_dict(),
                    'lineage_lock': lineage_lock_verdict.to_dict(),
                    'immutability': immutability_verdict.to_dict(),
                }
            except Exception as exc:
                bundle_payloads = [bundle]
                import_validation = {
                    'valid': False,
                    'issues': [f'validation failed: {exc}'],
                    'source': 'bundle_restore',
                    'status': 'invalid',
                }
        node_payloads = []
        if bundle_payloads:
            restored_payload = _safe_dict(bundle_payloads[0].get('payload')) or _safe_dict(bundle_payloads[0])
            local_payload = {
                'feedback_rows': [row.to_dict() for row in self._economic_memory_store.list_rows()],
                'roi_rows': [row.to_dict() for row in self._roi_history_store.list_rows()],
                'snapshot_rows': [row.to_dict() for row in self._economic_policy_snapshot_store.list_rows()],
                'trace_rows': [row.to_dict() for row in self._economic_trace_store.list_rows()],
                'metrics_rows': [row.to_dict() for row in self._economic_metrics_store.list_rows()],
                'export_manifest': _safe_dict(_safe_dict(bundle_payloads[0].get('payload')).get('export_manifest') or _safe_dict(bundle_payloads[0]).get('export_manifest')),
                'metadata': {'import_validation_status': 'valid'},
            }
            local_node_id = self._economic_store_bundle.node_id if self._economic_store_bundle is not None else 'local-primary'
            node_payloads = [
                {'node_id': local_node_id, 'payload': local_payload},
                {'node_id': 'bundle-restore', 'payload': {**restored_payload, 'metadata': {**_safe_dict(restored_payload.get('metadata')), 'import_validation_status': import_validation.get('status', 'valid' if import_validation.get('valid') else 'invalid')}}},
            ]
        reconciliation = self._economic_multi_backend_reconciliation.build(
            feedback_rows=[row.to_dict() for row in self._economic_memory_store.list_rows()],
            roi_rows=[row.to_dict() for row in self._roi_history_store.list_rows()],
            snapshot_rows=[row.to_dict() for row in self._economic_policy_snapshot_store.list_rows()],
            trace_rows=[row.to_dict() for row in self._economic_trace_store.list_rows()],
            metrics_rows=[row.to_dict() for row in self._economic_metrics_store.list_rows()],
            bundle_payloads=bundle_payloads,
            node_payloads=node_payloads,
            quorum_size=2,
        ).to_dict()
        reconciliation['import_validation'] = import_validation
        restored_manifest = _safe_dict(_safe_dict(bundle_payloads[0].get('payload')).get('export_manifest') or _safe_dict(bundle_payloads[0]).get('export_manifest')) if bundle_payloads else {}
        self._economic_forensics_service.record_event(
            event_type='economic_reconciliation_completed',
            severity='info' if reconciliation.get('consistent') else 'warning',
            artifact_id=str(_safe_dict(bundle).get('bundle_id') or _safe_dict(_safe_dict(bundle).get('payload')).get('bundle_id') or ''),
            artifact_digest=str(_safe_dict(bundle).get('digest') or ''),
            scope=_safe_dict(restored_manifest.get('scope')),
            schema_version=str(restored_manifest.get('bundle_schema_version') or ''),
            payload={'consistent': bool(reconciliation.get('consistent')), 'quorum_failure_segments': list(_safe_dict(reconciliation.get('metadata')).get('quorum_failure_segments') or ())},
            tags=('economic', 'reconciliation', 'forensics'),
        )
        return reconciliation

    def _assert_tenant_consistency(self, *, action: Mapping[str, Any], execution_receipt: Mapping[str, Any]) -> None:
        action_tenant_id = str(action.get('tenant_id') or '').strip()
        receipt_tenant_id = str(execution_receipt.get('tenant_id') or '').strip()
        if action_tenant_id and receipt_tenant_id and action_tenant_id != receipt_tenant_id:
            raise ValueError(f'cross-tenant closed loop receipt is forbidden: action={action_tenant_id} receipt={receipt_tenant_id}')
        effective_tenant_id = action_tenant_id or receipt_tenant_id
        if effective_tenant_id and self._tenant_registry is not None and hasattr(self._tenant_registry, 'assert_active'):
            self._tenant_registry.assert_active(effective_tenant_id)
        action_queue_name = str(action.get('queue_name') or '').strip()
        receipt_queue_name = str(execution_receipt.get('queue_name') or '').strip()
        if action_queue_name and receipt_queue_name and action_queue_name != receipt_queue_name:
            raise ValueError(f'queue mismatch in closed loop receipt is forbidden: action={action_queue_name} receipt={receipt_queue_name}')
        action_scope = self._tenant_scope_for(action=action, execution_receipt={})
        receipt_scope = self._tenant_scope_for(action={}, execution_receipt=execution_receipt)
        if action_scope is not None:
            for key_name in ('qualified_job_id', 'qualified_dedupe_key'):
                if action.get(key_name):
                    action_scope.assert_belongs_to_scope(str(action.get(key_name)))
        if receipt_scope is not None:
            for key_name in ('qualified_job_id', 'qualified_dedupe_key'):
                if execution_receipt.get(key_name):
                    receipt_scope.assert_belongs_to_scope(str(execution_receipt.get(key_name)))
        for scope_name, raw_scope, scope_obj in (
            ('action', action.get('tenant_scope') if isinstance(action.get('tenant_scope'), Mapping) else action.get('tenant_queue_scope') if isinstance(action.get('tenant_queue_scope'), Mapping) else None, action_scope),
            ('receipt', execution_receipt.get('tenant_scope') if isinstance(execution_receipt.get('tenant_scope'), Mapping) else execution_receipt.get('tenant_queue_scope') if isinstance(execution_receipt.get('tenant_queue_scope'), Mapping) else None, receipt_scope),
        ):
            if raw_scope is None or scope_obj is None:
                continue
            declared_scope_key = str(raw_scope.get('scope_key') or '').strip()
            if declared_scope_key and declared_scope_key != scope_obj.scope_key:
                raise ValueError(f'{scope_name} tenant scope_key mismatch is forbidden')
        if action_scope is not None and receipt_scope is not None and action_scope.scope_key != receipt_scope.scope_key:
            raise ValueError('tenant scope mismatch in closed loop receipt is forbidden')

    def _tenant_scope_for(self, *, action: Mapping[str, Any], execution_receipt: Mapping[str, Any]) -> TenantQueueScope | None:
        raw_scope = action.get('tenant_scope') if isinstance(action.get('tenant_scope'), Mapping) else action.get('tenant_queue_scope') if isinstance(action.get('tenant_queue_scope'), Mapping) else execution_receipt.get('tenant_scope') if isinstance(execution_receipt.get('tenant_scope'), Mapping) else execution_receipt.get('tenant_queue_scope') if isinstance(execution_receipt.get('tenant_queue_scope'), Mapping) else {}
        tenant_id = str(action.get('tenant_id') or execution_receipt.get('tenant_id') or raw_scope.get('tenant_id') or '').strip()
        queue_name = str(action.get('queue_name') or execution_receipt.get('queue_name') or raw_scope.get('queue_name') or '').strip()
        namespace = str(raw_scope.get('namespace') or 'runtime').strip() or 'runtime'
        if not tenant_id or not queue_name:
            return None
        return TenantQueueScope(tenant_id=tenant_id, queue_name=queue_name, namespace=namespace)

    def _resolve_tenant_budget(self, *, action: Mapping[str, Any], execution_receipt: Mapping[str, Any]):
        receipt_budget = _safe_dict(execution_receipt.get('tenant_budget'))
        if receipt_budget:
            return type('ReceiptBudgetVerdict', (), receipt_budget)()
        guard = self._tenant_execution_budget_guard
        tenant_id = str(action.get('tenant_id') or '').strip()
        if guard is None or not tenant_id:
            return None
        usage = TenantExecutionBudgetGuard.from_execution_payload(tenant_id=tenant_id, payload=action)
        budget_mode = str(action.get('tenant_budget_mode') or execution_receipt.get('tenant_budget_mode') or 'evaluate').strip().lower()
        verdict = guard.consume(usage=usage) if budget_mode == 'consume' else guard.evaluate(usage=usage)
        if not verdict.allowed:
            raise RuntimeError(f'tenant_execution_budget_denied:{verdict.reason}')
        return verdict

    @staticmethod
    def _budget_verdict_dict(verdict) -> dict[str, Any]:
        return {
            'allowed': bool(getattr(verdict, 'allowed', False)),
            'reason': str(getattr(verdict, 'reason', '')),
            'tenant_id': str(getattr(verdict, 'tenant_id', '')),
            'violations': list(getattr(verdict, 'violations', ()) or ()),
            'consumed': bool(getattr(verdict, 'consumed', False)),
        }


    def _build_cross_run_economic_audit(self) -> dict[str, Any]:
        feedback_rows = tuple(row.to_dict() for row in getattr(self._economic_memory_store, 'list_rows', lambda: ())())
        roi_rows = tuple(row.to_dict() for row in getattr(self._roi_history_store, 'list_rows', lambda: ())())
        snapshot_rows = tuple(row.to_dict() for row in getattr(self._economic_policy_snapshot_store, 'list_rows', lambda: ())())
        return self._cross_run_economic_audit.build(
            feedback_rows=feedback_rows,
            roi_rows=roi_rows,
            snapshot_rows=snapshot_rows,
        ).to_dict()

    @staticmethod
    def _extract_economic_payload(*, action: Mapping[str, Any], execution_receipt: Mapping[str, Any], verification: Mapping[str, Any], persisted_payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        for source in (action, execution_receipt, verification, persisted_payload):
            source_payload = _safe_dict(source)
            economic = _safe_dict(source_payload.get("economic_safety"))
            if economic:
                return _safe_dict(economic.get("budget_guard")), _safe_dict(economic.get("revenue_verification"))
            if source_payload.get("budget_guard") or source_payload.get("revenue_verification"):
                return _safe_dict(source_payload.get("budget_guard")), _safe_dict(source_payload.get("revenue_verification"))
        return {}, {}



__all__ = ['CANON_CLOSED_LOOP_ORCHESTRATOR', 'ClosedLoopCycleInput', 'ClosedLoopCycleResult', 'ClosedLoopOrchestrator']
