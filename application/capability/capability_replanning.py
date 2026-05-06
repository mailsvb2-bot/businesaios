from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CANON_CAPABILITY_REPLANNING = True



def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}



def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True)
class CapabilityReplanningDecision:
    mode: str
    reason: str
    operator_handoff_required: bool = False
    defer_goal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'mode': self.mode,
            'reason': self.reason,
            'operator_handoff_required': self.operator_handoff_required,
            'defer_goal': self.defer_goal,
        }


class CapabilityReplanningService:
    def evaluate(self, *, capability: Mapping[str, Any] | None, verification_result: Mapping[str, Any] | None = None) -> CapabilityReplanningDecision:
        capability_payload = _safe_dict(capability)
        verification = _safe_dict(verification_result)
        routing = _safe_dict(capability_payload.get('routing'))
        runtime = _safe_dict(capability_payload.get('runtime'))
        fallback = _safe_dict(capability_payload.get('fallback'))
        if capability_payload.get('allowed') is False or capability_payload.get('fallback_used'):
            return CapabilityReplanningDecision(
                mode='operator_handoff' if fallback.get('operator_handoff_required', True) else 'degraded_replan',
                reason=_text(fallback.get('internal_reason') or capability_payload.get('reason') or routing.get('reason') or verification.get('verification_status')),
                operator_handoff_required=bool(fallback.get('operator_handoff_required', True)),
                defer_goal=bool(fallback.get('defer_goal', False)),
            )
        if runtime.get('staleness_state') == 'stale':
            return CapabilityReplanningDecision(mode='degraded_replan', reason='stale_evidence')
        if runtime.get('evidence_state') in {'unknown', 'insufficient'}:
            return CapabilityReplanningDecision(mode='bounded_replan', reason='insufficient_evidence')
        if runtime.get('degraded') or runtime.get('routing_state') == 'fallback_preferred':
            return CapabilityReplanningDecision(mode='degraded_replan', reason=_text(runtime.get('last_feedback_reason') or verification.get('verification_status') or 'capability_degraded'))
        if verification.get('verification_status') == 'failed':
            return CapabilityReplanningDecision(mode='retry_replan', reason='verification_failed')
        return CapabilityReplanningDecision(mode='continue', reason='capability_ok')
    decide = evaluate


__all__ = ['CANON_CAPABILITY_REPLANNING', 'CapabilityReplanningDecision', 'CapabilityReplanningService']
