from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.capability.capability_diagnostics import CapabilityDiagnosticsBuilder
from application.capability.capability_execution_verdict import CapabilityExecutionVerdictBuilder
from application.capability.capability_fallback_contract import CapabilityFallbackDecision
from application.capability.capability_health_registry import CapabilityHealthRegistry
from application.capability.capability_matrix import CapabilityMatrix, CapabilityRecord, RuntimeCapabilitySnapshot
from application.capability.capability_tenant_policy import CapabilityTenantPolicyService
from config.decision_safety_policy import DEFAULT_CAPABILITY_BOOTSTRAP_POLICY, DEFAULT_CAPABILITY_FALLBACK_POLICY
from execution.routing.capability_quarantine import CapabilityQuarantine
from execution.routing.capability_registry import CapabilityRegistry, CapabilityRoute
from execution.routing.capability_router import CapabilityRouter as LowLevelCapabilityRouter
from execution.strategy_support_policy import StrategySupportPolicy

CANON_EXECUTION_CAPABILITY_ROUTER = True



def _text(value: object) -> str:
    return str(value or '').strip()



def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}



def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class RoutedCapabilityAction:
    action_type: str
    payload_patch: dict[str, Any]
    allowed: bool
    reason: str
    fallback_used: bool = False
    capability: dict[str, Any] | None = None
    routing_explanation: dict[str, Any] | None = None
    routing_scores: dict[str, dict[str, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'action_type': self.action_type,
            'payload_patch': dict(self.payload_patch),
            'allowed': self.allowed,
            'reason': self.reason,
            'fallback_used': self.fallback_used,
            'capability': dict(self.capability or {}),
            'routing_explanation': dict(self.routing_explanation or {}),
            'routing_scores': {k: dict(v) for k, v in (self.routing_scores or {}).items()},
        }


class ExecutionCapabilityRouter:
    def __init__(
        self,
        *,
        matrix: CapabilityMatrix | None = None,
        health_registry: CapabilityHealthRegistry | None = None,
        quarantine: CapabilityQuarantine | None = None,
        strategy_support_policy: StrategySupportPolicy | None = None,
        execution_verdict_builder: CapabilityExecutionVerdictBuilder | None = None,
        diagnostics_builder: CapabilityDiagnosticsBuilder | None = None,
        tenant_policy_service: CapabilityTenantPolicyService | None = None,
    ) -> None:
        self._matrix = matrix or CapabilityMatrix()
        self._health_registry = health_registry or CapabilityHealthRegistry(matrix=self._matrix)
        self._quarantine = quarantine or CapabilityQuarantine()
        self._strategy_support_policy = strategy_support_policy or StrategySupportPolicy()
        self._execution_verdict_builder = execution_verdict_builder or CapabilityExecutionVerdictBuilder()
        self._diagnostics_builder = diagnostics_builder or CapabilityDiagnosticsBuilder()
        self._tenant_policy_service = tenant_policy_service or CapabilityTenantPolicyService()

    def _runtime_snapshot(self, *, state: Any, request: Any) -> dict[str, Any]:
        state_meta = _safe_dict(getattr(state, 'meta', {}))
        request_meta = _safe_dict(getattr(request, 'meta', {}))
        return _safe_dict(state_meta.get('runtime_capabilities') or request_meta.get('runtime_capabilities') or {})

    def _materialize_record(self, *, request: Any, state: Any, action_type: str) -> CapabilityRecord:
        runtime_capabilities = self._runtime_snapshot(state=state, request=request)
        tenant_id = _text(getattr(request, 'tenant_id', ''))
        if tenant_id:
            runtime_capabilities = self._health_registry.runtime_capabilities_for_actions(
                tenant_id=tenant_id,
                action_types=[action_type],
                existing_runtime_capabilities=runtime_capabilities,
            )
        return self._matrix.record_for_action(action_type=action_type, runtime_capabilities=runtime_capabilities)

    @staticmethod
    def _stabilize_runtime(record: CapabilityRecord) -> CapabilityRecord:
        policy = DEFAULT_CAPABILITY_BOOTSTRAP_POLICY
        runtime = record.runtime
        descriptor = record.descriptor
        if runtime.observation_count > 0:
            return record
        if not descriptor.executable or not runtime.enabled:
            return record
        explicit_negative_runtime_signal = (
            runtime.staleness_state == 'stale'
            or runtime.degraded
            or runtime.evidence_state == 'insufficient'
            or runtime.routing_state == 'fallback_preferred'
            or (runtime.health_score > 0.0 and not runtime.healthy)
        )
        if explicit_negative_runtime_signal:
            return record
        if runtime.health_score > 0.0 and runtime.routing_state not in {'observe', 'fallback_preferred'}:
            return record
        bootstrap_payload = runtime.to_dict()
        bootstrap_payload.update({
            'healthy': True,
            'degraded': False,
            'health_score': max(runtime.health_score, policy.bootstrap_health_floor),
            'health_tier': 'healthy',
            'routing_state': policy.bootstrap_routing_state,
            'confidence_score': max(runtime.confidence_score, policy.bootstrap_confidence_floor),
            'evidence_state': runtime.evidence_state if runtime.evidence_state not in {'', 'sufficient'} else 'insufficient',
            'recommended_autonomy_tier': policy.bootstrap_recommended_autonomy_tier,
            'source': f"{runtime.source}:bootstrap",
            'bootstrap_mode': policy.bootstrap_mode,
        })
        return CapabilityRecord(
            descriptor=descriptor,
            runtime=RuntimeCapabilitySnapshot.from_payload(
                action_type=descriptor.action_type,
                capability_key=descriptor.capability_key,
                payload=bootstrap_payload,
            ),
        )

    @staticmethod
    def _build_registry(record: CapabilityRecord) -> CapabilityRegistry:
        descriptor = record.descriptor
        runtime = record.runtime
        route = CapabilityRoute(
            route_key=descriptor.action_type,
            capability_key=descriptor.capability_key,
            supported_action_types=(descriptor.action_type,),
            maturity='real' if descriptor.prod_ready else 'capability_shell',
            enabled=bool(runtime.enabled),
            base_cost=max(runtime.base_cost, runtime.estimated_cost),
            base_latency_ms=runtime.base_latency_ms,
            base_proofability=(1.0 if descriptor.externally_verified else max(0.0, runtime.base_proofability)),
            health_score=runtime.health_score,
            metadata={
                'action_type': descriptor.action_type,
                'capability_key': descriptor.capability_key,
                'health_tier': runtime.health_tier,
                'routing_state': runtime.routing_state,
                'runtime_source': runtime.source,
                'confidence_score': runtime.confidence_score,
                'staleness_state': runtime.staleness_state,
            },
        )
        registry = CapabilityRegistry()
        registry.register_many((route,))
        return registry

    @staticmethod
    def _fallback_decision_for(record: CapabilityRecord, routing_reason: str, *, autonomy_tier: str) -> CapabilityFallbackDecision | None:
        policy = DEFAULT_CAPABILITY_FALLBACK_POLICY
        capability_key = record.capability_key
        runtime = record.runtime
        action_type = record.action_type
        if action_type == policy.notify_owner_action_type:
            return None
        if runtime.staleness_state == policy.stale_state and capability_key != policy.internal_execution_capability_key:
            return CapabilityFallbackDecision(kind=policy.degraded_execution_kind, public_reason='stale_evidence_notify_owner', internal_reason='stale_evidence', target_action_type=policy.notify_owner_action_type)
        if runtime.evidence_state in {'unknown', 'insufficient'} and autonomy_tier == policy.full_autonomy_tier and capability_key != policy.internal_execution_capability_key:
            return CapabilityFallbackDecision(kind=policy.operator_handoff_kind, public_reason='insufficient_evidence_notify_owner', internal_reason='insufficient_evidence_for_full_autonomy', target_action_type=policy.notify_owner_action_type)
        if routing_reason == 'route_disabled' and capability_key == policy.communications_capability_key:
            return CapabilityFallbackDecision(kind=policy.operator_handoff_kind, public_reason='capability_fallback_notify_owner', internal_reason='communications_disabled')
        if routing_reason == 'route_unhealthy':
            if runtime.health_score < policy.low_health_operator_handoff_threshold:
                return CapabilityFallbackDecision(kind=policy.operator_handoff_kind, public_reason='low_health_score_notify_owner', internal_reason='low_health_score')
            if capability_key in set(policy.protected_capability_keys):
                return CapabilityFallbackDecision(kind=policy.degraded_execution_kind, public_reason='degraded_mode_notify_owner', internal_reason='connector_unhealthy')
        if runtime.routing_state == policy.fallback_preferred_state and capability_key != policy.internal_execution_capability_key:
            if runtime.health_score < policy.low_health_operator_handoff_threshold:
                return CapabilityFallbackDecision(kind=policy.operator_handoff_kind, public_reason='low_health_score_notify_owner', internal_reason='low_health_score')
            return CapabilityFallbackDecision(kind=policy.degraded_execution_kind, public_reason='degraded_mode_notify_owner', internal_reason='fallback_preferred')
        return None

    def _build_capability_payload(self, *, record: CapabilityRecord, routing_explanation: Mapping[str, Any] | None, routing_scores: Mapping[str, Mapping[str, float]] | None, fallback: CapabilityFallbackDecision | None = None, allowed: bool = True, fallback_used: bool = False, reason: str = 'capability_ok', execution_verdict: Mapping[str, Any] | None = None, policy_verdict: Mapping[str, Any] | None = None) -> dict[str, Any]:
        runtime_meta = dict(record.runtime.metadata)
        strategy_hints = [
            hint.to_dict()
            for hint in self._strategy_support_policy.build_hints(
                goal_family=str(runtime_meta.get('goal_family') or 'default'),
                metadata={
                    **runtime_meta,
                    'approval_required': record.descriptor.approval_required,
                    'requires_approval': record.descriptor.approval_required,
                    'routing_state': record.runtime.routing_state,
                    'confidence_score': record.runtime.confidence_score,
                    'staleness_state': record.runtime.staleness_state,
                    'evidence_state': record.runtime.evidence_state,
                },
            )
        ]
        payload = {
            **record.to_dict(),
            'allowed': bool(allowed),
            'fallback_used': bool(fallback_used),
            'reason': str(reason),
            'routing': dict(routing_explanation or {}),
            'routing_scores': {k: dict(v) for k, v in (routing_scores or {}).items()},
            'strategy_hints': strategy_hints,
        }
        if fallback is not None:
            payload['fallback'] = fallback.to_dict()
        if execution_verdict is not None:
            payload['execution_verdict'] = dict(execution_verdict)
        if policy_verdict is not None:
            payload['policy_verdict'] = dict(policy_verdict)
        diagnostics = self._diagnostics_builder.build(
            record=record,
            allowed=allowed,
            reason=reason,
            routing_explanation=routing_explanation,
            execution_verdict=execution_verdict,
            fallback=fallback,
            policy_verdict=policy_verdict,
        ).to_dict()
        payload['diagnostics'] = diagnostics
        return payload

    def _blocked(self, *, record: CapabilityRecord, reason: str, routing_explanation: Mapping[str, Any] | None = None, routing_scores: Mapping[str, Mapping[str, float]] | None = None, extra_payload_patch: Mapping[str, Any] | None = None) -> RoutedCapabilityAction:
        capability_payload = self._build_capability_payload(record=record, routing_explanation=routing_explanation, routing_scores=routing_scores, allowed=False, fallback_used=False, reason=reason, execution_verdict=_safe_dict(extra_payload_patch).get('execution_verdict'), policy_verdict=_safe_dict(extra_payload_patch).get('policy_verdict'))
        payload_patch = {'capability_blocked': True, 'capability_diagnostics': dict(capability_payload.get('diagnostics') or {}), **_safe_dict(extra_payload_patch)}
        if routing_explanation:
            payload_patch['routing_explanation'] = dict(routing_explanation)
        return RoutedCapabilityAction(
            action_type=record.action_type,
            payload_patch=payload_patch,
            allowed=False,
            reason=reason,
            fallback_used=False,
            capability=capability_payload,
            routing_explanation=dict(routing_explanation or {}),
            routing_scores={k: dict(v) for k, v in (routing_scores or {}).items()},
        )

    def _fallback_action(self, *, record: CapabilityRecord, payload_dict: Mapping[str, Any], fallback: CapabilityFallbackDecision, routing_explanation: Mapping[str, Any], routing_scores: Mapping[str, Mapping[str, float]]) -> RoutedCapabilityAction:
        execution_verdict = _safe_dict(payload_dict).get('execution_verdict')
        capability_payload = self._build_capability_payload(record=record, routing_explanation=routing_explanation, routing_scores=routing_scores, fallback=fallback, allowed=True, fallback_used=True, reason=fallback.public_reason, execution_verdict=execution_verdict, policy_verdict=_safe_dict(payload_dict).get('policy_verdict'))
        return RoutedCapabilityAction(
            action_type=fallback.target_action_type,
            payload_patch={
                **payload_dict,
                'capability_fallback_from': record.action_type,
                'capability_fallback_reason': fallback.internal_reason,
                'capability_fallback_kind': fallback.kind,
                'operator_required': bool(fallback.operator_handoff_required),
                'status': 'capability_fallback_selected',
                'capability_diagnostics': dict(capability_payload.get('diagnostics') or {}),
                'routing_explanation': dict(routing_explanation),
            },
            allowed=True,
            reason=fallback.public_reason,
            fallback_used=True,
            capability=capability_payload,
            routing_explanation=dict(routing_explanation),
            routing_scores={k: dict(v) for k, v in routing_scores.items()},
        )

    def _enforce_execution_verdict(self, *, record: CapabilityRecord, payload_dict: Mapping[str, Any], verdict: Mapping[str, Any], fallback: CapabilityFallbackDecision | None) -> RoutedCapabilityAction | None:
        verdict_dict = dict(verdict)
        budget_allowed = bool(verdict_dict.get('budget_allowed', True))
        blast_radius_allowed = bool(verdict_dict.get('blast_radius_allowed', True))
        if budget_allowed and blast_radius_allowed:
            return None
        reason = _text(verdict_dict.get('reason') or 'execution_verdict_denied')
        return self._blocked(record=record, reason=reason, extra_payload_patch={'execution_verdict': verdict_dict, 'runtime_capability': record.runtime.to_dict()})

    def _build_execution_verdict(self, *, request: Any, action_type: str, payload_dict: Mapping[str, Any], capability_allowed: bool, fallback: CapabilityFallbackDecision | None = None, policy_verdict: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._execution_verdict_builder.build(
            request=request,
            action_type=action_type,
            payload=payload_dict,
            capability_allowed=capability_allowed,
            fallback_action_type=(fallback.target_action_type if fallback is not None else None),
            policy_verdict=policy_verdict,
        ).to_dict()

    def route(self, *, request: Any, state: Any, action_type: str, payload: Mapping[str, Any] | None) -> RoutedCapabilityAction:
        payload_dict = _safe_dict(payload)
        record = self._stabilize_runtime(self._materialize_record(request=request, state=state, action_type=action_type))
        descriptor = record.descriptor
        runtime = record.runtime
        autonomy_tier = _text(getattr(request, 'autonomy_tier', 'supervised')) or 'supervised'

        if not descriptor.decisionable:
            return self._blocked(record=record, reason='action_not_decisionable')
        if not descriptor.routable:
            return self._blocked(record=record, reason='action_not_routable')
        if not descriptor.executable:
            return self._blocked(record=record, reason='action_not_executable')
        policy_verdict = self._tenant_policy_service.evaluate(request=request, record=record, payload=payload_dict).to_dict()
        if policy_verdict.get('allowed') is False:
            verdict = self._build_execution_verdict(request=request, action_type=record.action_type, payload_dict=payload_dict, capability_allowed=False, policy_verdict=policy_verdict)
            return self._blocked(record=record, reason=_text(policy_verdict.get('reason') or 'tenant_capability_policy_denied'), extra_payload_patch={'policy_verdict': policy_verdict, 'execution_verdict': verdict, 'runtime_capability': runtime.to_dict(), 'recommended_autonomy_tier': policy_verdict.get('recommended_autonomy_tier')})

        if not runtime.enabled:
            fallback = self._fallback_decision_for(record, 'route_disabled', autonomy_tier=autonomy_tier)
            if fallback is not None:
                return self._fallback_action(record=record, payload_dict=payload_dict, fallback=fallback, routing_explanation={'reason': 'route_disabled'}, routing_scores={})
            return self._blocked(record=record, reason='runtime_capability_disabled', extra_payload_patch={'runtime_capability': runtime.to_dict()})

        if runtime.evidence_state in {'unknown', 'insufficient'} and autonomy_tier == 'full_autonomy' and descriptor.capability_key != 'internal_execution':
            verdict = self._build_execution_verdict(request=request, action_type=record.action_type, payload_dict=payload_dict, capability_allowed=False, policy_verdict=policy_verdict)
            return self._blocked(
                record=record,
                reason='insufficient_evidence_for_full_autonomy',
                extra_payload_patch={'runtime_capability': runtime.to_dict(), 'recommended_autonomy_tier': runtime.recommended_autonomy_tier, 'execution_verdict': verdict},
            )

        if not descriptor.prod_ready and autonomy_tier == 'full_autonomy':
            verdict = self._build_execution_verdict(request=request, action_type=record.action_type, payload_dict=payload_dict, capability_allowed=False, policy_verdict=policy_verdict)
            return self._blocked(record=record, reason='non_prod_ready_under_full_autonomy', extra_payload_patch={'prod_ready_required': True, 'execution_verdict': verdict})

        fallback = self._fallback_decision_for(record, '', autonomy_tier=autonomy_tier)
        execution_verdict = self._build_execution_verdict(request=request, action_type=record.action_type, payload_dict=payload_dict, capability_allowed=True, fallback=fallback, policy_verdict=policy_verdict)
        enforced = self._enforce_execution_verdict(record=record, payload_dict={**payload_dict, 'execution_verdict': execution_verdict}, verdict=execution_verdict, fallback=fallback if fallback is not None and fallback.kind in {'operator_handoff', 'degraded_execution'} else None)
        if enforced is not None:
            return enforced
        if fallback is not None and fallback.internal_reason in {'stale_evidence', 'fallback_preferred', 'low_health_score', 'connector_unhealthy'}:
            return self._fallback_action(record=record, payload_dict={**payload_dict, 'execution_verdict': execution_verdict}, fallback=fallback, routing_explanation={'reason': fallback.internal_reason}, routing_scores={})

        low_level_router = LowLevelCapabilityRouter(registry=self._build_registry(record), quarantine=self._quarantine)
        routing_decision = low_level_router.select_best_route(
            capability_key=record.capability_key,
            action_type=record.action_type,
            requested_units=max(0.0, _safe_float(payload_dict.get('estimated_cost'), default=1.0)),
            runtime_routes={record.action_type: runtime.to_dict()},
        )
        routing_explanation = routing_decision.explanation.to_dict()
        routing_scores = {key: dict(value) for key, value in routing_decision.score_breakdown.items()}
        capability_payload = self._build_capability_payload(record=record, routing_explanation=routing_explanation, routing_scores=routing_scores, allowed=True, fallback_used=False, reason='capability_ok', execution_verdict=execution_verdict, policy_verdict=policy_verdict)

        if routing_decision.selected_route is None:
            rejected_routes = _safe_dict(_safe_dict(routing_explanation.get('factors')).get('rejected_routes'))
            routing_reason = _text(rejected_routes.get(record.action_type) or _safe_dict(routing_explanation.get('factors')).get('reason'))
            fallback = self._fallback_decision_for(record, routing_reason, autonomy_tier=autonomy_tier)
            if fallback is not None:
                return self._fallback_action(record=record, payload_dict={**payload_dict, 'execution_verdict': execution_verdict}, fallback=fallback, routing_explanation=routing_explanation, routing_scores=routing_scores)
            return self._blocked(
                record=record,
                reason='runtime_capability_disabled' if routing_reason == 'route_disabled' else 'runtime_route_unavailable',
                routing_explanation=routing_explanation,
                routing_scores=routing_scores,
                extra_payload_patch={'runtime_capability': runtime.to_dict(), 'execution_verdict': execution_verdict},
            )

        return RoutedCapabilityAction(
            action_type=record.action_type,
            payload_patch={'routing_explanation': routing_explanation, 'execution_verdict': execution_verdict, 'policy_verdict': policy_verdict, 'capability_diagnostics': dict(capability_payload.get('diagnostics') or {})},
            allowed=True,
            reason='capability_ok',
            fallback_used=False,
            capability=capability_payload,
            routing_explanation=routing_explanation,
            routing_scores=routing_scores,
        )


__all__ = ['CANON_EXECUTION_CAPABILITY_ROUTER', 'ExecutionCapabilityRouter', 'RoutedCapabilityAction']
