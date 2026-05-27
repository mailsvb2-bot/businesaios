from __future__ import annotations

from typing import Any

from runtime.platform.business_memory.models import BusinessMemoryRecord
from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload
from runtime.platform.business_memory.semantics import infer_memory_status

CANON_BUSINESS_MEMORY_PROJECTIONS = True


def _bounded_unique_strings(items: list[str], *, limit: int = 25) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        token = str(item or '').strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= limit:
            break
    return result


def merge_request_profile(*, memory: BusinessMemoryRecord, request_profile: dict[str, Any] | None) -> dict[str, Any]:
    return {**dict(memory.profile or {}), **dict(request_profile or {})}


def to_runtime_context(memory: BusinessMemoryRecord) -> dict[str, Any]:
    payload = sanitize_business_memory_payload(memory.to_dict())
    payload['verified_outcomes_count'] = len(payload.get('last_verified_outcomes') or [])
    payload['recent_external_refs_count'] = len(payload.get('recent_external_refs') or [])
    payload['operator_handoffs_count'] = len(payload.get('escalation_history') or [])
    payload['recent_runs_count'] = len(payload.get('recent_runs') or [])
    payload['recurring_wins_count'] = len(payload.get('recurring_wins') or [])
    payload['recurring_failures_count'] = len(payload.get('recurring_failures') or [])
    return payload


def apply_step_feedback(
    *,
    memory: BusinessMemoryRecord,
    feedback: dict[str, Any],
    action_type: str,
    request_meta: dict[str, Any] | None = None,
) -> BusinessMemoryRecord:
    current = memory.to_dict()
    normalized = dict(feedback.get('normalized_outcome') or {})
    verified = bool(feedback.get('verified', False))
    executed = bool(feedback.get('executed', False))
    attempted = bool(feedback.get('attempted', False))
    operator_required = bool(feedback.get('operator_required', False))
    memory_status = infer_memory_status(feedback)
    refs = feedback.get('external_refs') or []
    if isinstance(refs, tuple):
        refs = list(refs)
    if not isinstance(refs, list):
        refs = []
    action_name = str(action_type or '').strip()
    channels = list(current.get('active_channels') or [])
    channel = str(feedback.get('channel') or normalized.get('channel') or '').strip()
    if channel:
        channels.append(channel)
    current['active_channels'] = _bounded_unique_strings(channels, limit=12)

    recent_runs = list(current.get('recent_runs') or [])
    recent_runs.insert(
        0,
        {
            'action': action_name,
            'status': memory_status,
            'attempted': attempted,
            'executed': executed,
            'verified': verified,
            'operator_required': operator_required,
            'goal': str(feedback.get('goal') or request_meta.get('goal') if isinstance(request_meta, dict) else ''),
            'channel': channel,
            'primary_ref': str(refs[0]) if refs else '',
            'reason': str(feedback.get('error') or feedback.get('reason') or ''),
            'goal_score': float(feedback.get('goal_score') or 0.0),
            'constraint_keys': sorted(str(key) for key in (dict(request_meta.get('constraints') or {}) if isinstance(request_meta, dict) else {}).keys()),
        },
    )
    current['recent_runs'] = recent_runs

    if verified:
        verified_outcome = {
            'action': action_name,
            'status': memory_status or 'verified',
            'external_refs': list(refs),
            'goal_score': float(feedback.get('goal_score') or 0.0),
            'outcome': normalized,
        }
        current['last_verified_outcomes'] = ([verified_outcome] + list(current.get('last_verified_outcomes') or []))[:20]
        current['recent_external_refs'] = _bounded_unique_strings(list(refs) + list(current.get('recent_external_refs') or []), limit=25)
        if 'launch_campaign' in action_name:
            current['current_campaigns'] = ([{'action': action_name, 'external_refs': list(refs), 'status': 'verified'}] + list(current.get('current_campaigns') or []))[:10]
        if 'listing' in action_name:
            current['active_listings'] = ([{'action': action_name, 'external_refs': list(refs), 'status': 'verified'}] + list(current.get('active_listings') or []))[:10]
        if 'route_lead' in action_name or normalized.get('lead_count'):
            current['open_leads'] = ([{'action': action_name, 'external_refs': list(refs), 'status': 'verified'}] + list(current.get('open_leads') or []))[:20]
    else:
        if operator_required or feedback.get('retry_classification', {}).get('kind') == 'operator_required':
            history = list(current.get('escalation_history') or [])
            history.insert(0, {'action': action_name, 'reason': feedback.get('retry_classification', {}).get('reason') or feedback.get('reason') or memory_status})
            current['escalation_history'] = history[:20]
        else:
            failure = {
                'action': action_name,
                'status': memory_status,
                'reason': str(feedback.get('error') or feedback.get('reason') or ''),
            }
            current['failed_strategies'] = ([failure] + list(current.get('failed_strategies') or []))[:20]
    return BusinessMemoryRecord.from_dict(current, business_id=memory.business_id)


__all__ = [
    'CANON_BUSINESS_MEMORY_PROJECTIONS',
    'apply_step_feedback',
    'merge_request_profile',
    'to_runtime_context',
]
