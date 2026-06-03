from __future__ import annotations

from typing import Any
from collections.abc import Mapping


CANON_AUTONOMY_SAFETY_DECISION = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def canonical_autonomy_safety_decision(
    *,
    request: Any | None = None,
    safety_verdict: Mapping[str, Any] | None = None,
    bounded_autonomy: Mapping[str, Any] | None = None,
    blast_radius_guard: Mapping[str, Any] | None = None,
    safe_self_driving: Mapping[str, Any] | None = None,
    next_tier_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    verdict = _safe_dict(safety_verdict)
    details = _safe_dict(verdict.get('details'))
    bounded = _safe_dict(bounded_autonomy or details.get('bounded_autonomy'))
    blast = _safe_dict(blast_radius_guard or details.get('blast_radius_guard'))
    safe_loop = _safe_dict(safe_self_driving or details.get('safe_self_driving'))
    next_ctx = _safe_dict(next_tier_context)
    requested = _text(getattr(request, 'autonomy_tier', '') if request is not None else '', default='supervised')
    next_tier = _text(verdict.get('next_tier') or safe_loop.get('next_tier') or next_ctx.get('suggested_tier') or requested, default='supervised')
    operator_required = bool(verdict.get('operator_required', False) or bounded.get('operator_required', False) or safe_loop.get('should_stop', False))
    blocked = not bool(verdict.get('allowed', True))
    return {
        'requested_tier': requested,
        'next_tier': next_tier,
        'allowed': not blocked,
        'blocked': blocked,
        'operator_required': operator_required,
        'bounded_autonomy_reason': _text(bounded.get('reason')),
        'blast_radius_reason': _text(blast.get('reason')),
        'safe_self_driving_reason': _text(safe_loop.get('reason')),
        'handoff_triggered': operator_required or blocked,
        'decision_reason': _text(verdict.get('reason')),
        'approval_required': bool(_safe_dict(details.get('autonomy_tier')).get('approval_required', False)),
        'blocked_by_policy': bool(_safe_dict(details.get('autonomy_tier')).get('blocked_by_policy', False)),
        'blast_radius_allowed': bool(blast.get('allowed', not _text(blast.get('reason')) == 'blast_radius_exceeded')),
        'safe_loop_stop': bool(safe_loop.get('should_stop', False)),
        'safe_loop_downgrade': bool(safe_loop.get('should_downgrade', False)),
        'next_tier_context': next_ctx,
    }


__all__ = ['CANON_AUTONOMY_SAFETY_DECISION', 'canonical_autonomy_safety_decision']
