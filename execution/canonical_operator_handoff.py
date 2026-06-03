from __future__ import annotations

from typing import Any
from collections.abc import Mapping


CANON_OPERATOR_HANDOFF_CONTRACT = True

_ALLOWED_HANDOFF_STATES = {
    'handoff_required',
    'blocked',
    'awaiting_operator',
    'resolved',
    'escalated',
}
_ALLOWED_RESOLUTIONS = {
    'approved',
    'rejected',
    'cancelled',
    'resolved',
    'manual_override',
    'retry',
    'noop',
}


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def canonical_operator_handoff(
    payload: Mapping[str, Any] | None,
    *,
    next_tier_context: Mapping[str, Any] | None = None,
    opportunity_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    src = _safe_dict(payload)
    context = _safe_dict(next_tier_context or src.get('next_tier_context'))
    next_tier = _text(src.get('next_tier') or context.get('suggested_tier') or src.get('autonomy_tier'), default='supervised')
    handoff_state = _text(src.get('handoff_state') or src.get('status'), default='handoff_required')
    if handoff_state not in _ALLOWED_HANDOFF_STATES:
        handoff_state = 'handoff_required'
    blocked = bool(src.get('blocked_by_policy', False) or handoff_state == 'blocked')
    escalation_required = bool(src.get('escalation_required', False) or next_tier != _text(src.get('autonomy_tier'), default='supervised'))
    manual_override_allowed = bool(src.get('manual_override_allowed', True))
    manual_override_used = bool(src.get('manual_override_used', False))
    reasons = tuple(
        item for item in (
            _text(src.get('handoff_reason')),
            _text(src.get('reason')),
            _text(src.get('bounded_autonomy_reason')),
            _text(src.get('blast_radius_reason')),
            _text(src.get('safe_self_driving_reason')),
        )
        if item
    )
    return {
        'run_id': _text(src.get('run_id')),
        'step_index': int(src.get('step_index') or 0),
        'decision_id': _text(src.get('decision_id')),
        'action': _text(src.get('action')),
        'autonomy_tier': _text(src.get('autonomy_tier'), default='supervised'),
        'next_tier': next_tier,
        'handoff_state': handoff_state,
        'blocked': blocked,
        'operator_required': True,
        'approval_required': bool(src.get('approval_required', False)),
        'blocked_by_policy': bool(src.get('blocked_by_policy', False)),
        'verification_failed': bool(src.get('verification_failed', False)),
        'escalation_required': escalation_required,
        'manual_override_allowed': manual_override_allowed,
        'manual_override_used': manual_override_used,
        'handoff_reason': _text(src.get('handoff_reason') or src.get('reason')),
        'reason': _text(src.get('reason') or src.get('handoff_reason')),
        'reasons': list(dict.fromkeys(reasons)),
        'bounded_autonomy_reason': _text(src.get('bounded_autonomy_reason')),
        'blast_radius_reason': _text(src.get('blast_radius_reason')),
        'safe_self_driving_reason': _text(src.get('safe_self_driving_reason')),
        'next_tier_context': context,
        'opportunity_signals': [dict(item) for item in _safe_list(opportunity_signals or src.get('opportunity_signals')) if isinstance(item, Mapping)],
    }



def canonical_operator_resolution(
    handoff_record: Mapping[str, Any] | None,
    *,
    resolution: str,
    note: str = '',
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    handoff = canonical_operator_handoff(handoff_record)
    normalized_resolution = _text(resolution, default='resolved')
    if normalized_resolution not in _ALLOWED_RESOLUTIONS:
        normalized_resolution = 'resolved'
    manual_override_used = normalized_resolution == 'manual_override' or bool(_safe_dict(payload).get('manual_override_used', False))
    handoff_state = 'resolved'
    if normalized_resolution == 'retry':
        handoff_state = 'escalated'
    elif normalized_resolution == 'rejected':
        handoff_state = 'blocked'
    return {
        'run_id': handoff['run_id'],
        'step_index': handoff['step_index'],
        'decision_id': handoff['decision_id'],
        'action': handoff['action'],
        'handoff_state': handoff_state,
        'resolution': normalized_resolution,
        'note': _text(note),
        'payload': dict(_safe_dict(payload)),
        'manual_override_used': manual_override_used,
        'operator_required': False,
        'source_handoff_reason': handoff['handoff_reason'],
    }


__all__ = [
    'CANON_OPERATOR_HANDOFF_CONTRACT',
    'canonical_operator_handoff',
    'canonical_operator_resolution',
]
