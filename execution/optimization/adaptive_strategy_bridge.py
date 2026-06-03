from __future__ import annotations

from typing import Any
from collections.abc import Mapping


CANON_ADAPTIVE_STRATEGY_BRIDGE = True


class AdaptiveStrategyBridge:
    """Translate adaptation profiles into evidence-only strategy advice."""

    @staticmethod
    def _safe_dict(value: object) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def build_advisory(self, *, runtime_policy_view: Mapping[str, Any]) -> dict[str, Any]:
        policy = self._safe_dict(runtime_policy_view)
        routing_table = {str(k): float(v) for k, v in self._safe_dict(policy.get('routing_table')).items()}
        sorted_routes = sorted(routing_table.items(), key=lambda item: item[1], reverse=True)
        preferred_route = sorted_routes[0][0] if sorted_routes else ''
        economic = self._safe_dict(policy.get('economic'))
        thresholds = self._safe_dict(policy.get('thresholds'))
        counters = self._safe_dict(policy.get('counters'))
        adaptation_ready = bool(policy.get('adaptation_ready'))
        accepted_observations = int(counters.get('accepted_observations') or 0)
        verification_threshold = float(thresholds.get('verification_threshold') or 0.0)
        retry_threshold = float(thresholds.get('retry_threshold') or 0.0)
        spend_tightness = float(economic.get('spend_tightness') or 0.0)
        min_expected_roi = float(economic.get('min_expected_roi') or 0.0)

        focus_mode = 'stabilize'
        if adaptation_ready and preferred_route and accepted_observations >= 5 and min_expected_roi >= 0.35 and spend_tightness <= 0.65:
            focus_mode = 'scale_verified_route'
        elif preferred_route and verification_threshold >= 0.65:
            focus_mode = 'verify_before_scale'
        elif retry_threshold >= 0.65:
            focus_mode = 'retry_carefully'

        return {
            'preferred_route_key': preferred_route or None,
            'preferred_routes': [route for route, _weight in sorted_routes[:3]],
            'focus_mode': focus_mode,
            'economic_guardrails': {
                'budget_multiplier': float(economic.get('budget_multiplier') or 1.0),
                'min_expected_roi': min_expected_roi,
                'spend_tightness': spend_tightness,
            },
            'policy_readiness': {
                'adaptation_ready': adaptation_ready,
                'accepted_observations': accepted_observations,
                'last_noise_reason': str(policy.get('last_noise_reason') or ''),
            },
            'evidence_only': True,
            'must_not_issue_decision': True,
        }
