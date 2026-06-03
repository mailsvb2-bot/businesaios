from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from execution.optimization.adaptive_optimizer import AdaptiveOptimizer
from execution.optimization.adaptive_strategy_bridge import AdaptiveStrategyBridge


CANON_ADAPTIVE_OPTIMIZATION_SERVICE = True


class AdaptiveOptimizationService:
    """Evidence-only adaptation service.

    This service must never issue decisions and must never call the sovereign decider.
    It only converts verified execution feedback into advisory runtime context.
    """

    def __init__(self, *, optimizer: AdaptiveOptimizer, strategy_bridge: AdaptiveStrategyBridge | None = None) -> None:
        self._optimizer = optimizer
        self._strategy_bridge = strategy_bridge or AdaptiveStrategyBridge()

    @staticmethod
    def _safe_dict(value: object) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def load_context(self, *, tenant_id: str, business_id: str, capability_key: str) -> dict[str, Any]:
        view = dict(self._optimizer.load_runtime_policy(tenant_id=tenant_id, business_id=business_id, capability_key=capability_key) or {})
        view['strategy_advisory'] = self._strategy_bridge.build_advisory(runtime_policy_view=view)
        return view

    def update_after_step(self, *, tenant_id: str, business_id: str, feedback: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = self._safe_dict(feedback)
        action_type = str(payload.get('action_type') or payload.get('capability_key') or payload.get('route_key') or '').strip()
        if not action_type:
            return {
                'accepted': False,
                'noise_reason': 'missing_action_type',
                'adaptation_ready': False,
                'evidence_only': True,
                'must_not_issue_decision': True,
            }
        normalized = {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'capability_key': action_type,
            'route_key': str(payload.get('route_key') or action_type),
            'action_type': action_type,
            'decision_id': payload.get('decision_id'),
            'correlation_id': payload.get('correlation_id'),
            'executed': payload.get('executed'),
            'verified': payload.get('verified'),
            'achieved': payload.get('goal_evaluation', {}).get('achieved', payload.get('achieved', payload.get('goal_reached'))),
            'goal_reached': payload.get('goal_reached'),
            'verification_confidence': payload.get('verification_confidence'),
            'latency_ms': payload.get('latency_ms'),
            'external_refs': list(payload.get('external_refs') or []),
            'economic': {
                'cost': payload.get('economic', {}).get('cost', payload.get('estimated_cost', payload.get('cost', 0.0))),
                'revenue_delta': payload.get('revenue_outcome', {}).get('delta', payload.get('economic', {}).get('revenue_delta', payload.get('revenue_delta', 0.0))),
            },
            'thresholds': {
                'before': payload.get('threshold_before', 0.60),
                'after': payload.get('threshold_after', 0.60),
            },
        }
        result = self._optimizer.update_from_feedback(feedback=normalized)
        view = dict(result.runtime_policy_view)
        view['accepted'] = bool(result.accepted)
        view['noise_reason'] = str(result.noise_reason)
        view['strategy_advisory'] = self._strategy_bridge.build_advisory(runtime_policy_view=view)
        return view


__all__ = ['AdaptiveOptimizationService', 'CANON_ADAPTIVE_OPTIMIZATION_SERVICE']
