from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Any, Mapping

from reliability.idempotency_scope import IdempotencyScope

CANON_CLOSED_LOOP_ECONOMIC_STATE = True


def safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except Exception:
        return None
    return parsed if parsed > 0 else None


def stable_reliability_trace(*, action: Mapping[str, Any], verification: Mapping[str, Any], execution_receipt: Mapping[str, Any]) -> dict[str, Any]:
    verification_payload = safe_dict(verification.get('verification'))
    leader_payload = safe_dict(execution_receipt.get('leader_election'))
    fencing_payload = safe_dict(execution_receipt.get('fencing'))
    fencing_token = (
        safe_int(fencing_payload.get('token'))
        or safe_int(execution_receipt.get('fencing_token'))
        or safe_int(action.get('fencing_token'))
    )
    base = {
        'action_type': str(action.get('action_type') or ''),
        'action_id': str(action.get('action_id') or ''),
        'decision_id': str(action.get('decision_id') or execution_receipt.get('decision_id') or ''),
        'correlation_id': str(action.get('correlation_id') or execution_receipt.get('correlation_id') or ''),
        'verification_status': str(verification_payload.get('status') or verification.get('verification_status') or ''),
        'leader_election_name': str(leader_payload.get('election_name') or execution_receipt.get('leader_election_name') or ''),
        'leader_id': str(leader_payload.get('leader_id') or execution_receipt.get('leader_id') or ''),
        'fencing_token': fencing_token,
    }
    scope = IdempotencyScope.from_parts(base)
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {**base, 'trace_key': hashlib.sha256(raw).hexdigest(), 'semantic_scope': scope.as_dict()}


def economic_event_id(*, action: Mapping[str, Any], persisted_payload: Mapping[str, Any], reliability_trace: Mapping[str, Any]) -> str:
    effect_delivery = safe_dict(persisted_payload.get('effect_delivery'))
    receipt = safe_dict(persisted_payload.get('persistence_receipt'))
    base = {
        'tenant_id': str(action.get('tenant_id') or '').strip(),
        'run_id': str(action.get('run_id') or action.get('decision_id') or '').strip(),
        'action_id': str(action.get('action_id') or '').strip(),
        'effect_key': str(effect_delivery.get('effect_key') or receipt.get('effect_key') or '').strip(),
        'trace_key': str(reliability_trace.get('trace_key') or '').strip(),
    }
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:24]


def append_unique_history(rows: list[dict[str, Any]], item: Mapping[str, Any], *, key_fields: tuple[str, ...], limit: int = 100) -> list[dict[str, Any]]:
    normalized = dict(item)
    needle = tuple(str(normalized.get(field) or '').strip() for field in key_fields)
    filtered = [dict(row) for row in rows if tuple(str(dict(row).get(field) or '').strip() for field in key_fields) != needle]
    filtered.append(normalized)
    return filtered[-limit:]


def apply_economic_history_to_state(*, world_state: Any, economic_feedback: Mapping[str, Any], roi_history: Mapping[str, Any], policy_snapshot: Mapping[str, Any]) -> Any:
    meta_updates = {
        'economic_feedback_history': None,
        'economic_roi_history': None,
        'economic_policy_snapshot_history': None,
        'last_economic_feedback': dict(economic_feedback),
        'last_economic_roi_history': dict(roi_history),
        'last_economic_policy_snapshot': dict(policy_snapshot),
    }
    if isinstance(world_state, Mapping):
        state = dict(world_state)
        meta = safe_dict(state.get('meta'))
        meta_updates['economic_feedback_history'] = append_unique_history(list(meta.get('economic_feedback_history') or []), economic_feedback, key_fields=('event_id',), limit=100)
        meta_updates['economic_roi_history'] = append_unique_history(list(meta.get('economic_roi_history') or []), roi_history, key_fields=('event_id',), limit=100)
        meta_updates['economic_policy_snapshot_history'] = append_unique_history(list(meta.get('economic_policy_snapshot_history') or []), policy_snapshot, key_fields=('snapshot_id',), limit=100)
        meta.update(meta_updates)
        state['meta'] = meta
        return state
    if hasattr(world_state, 'meta'):
        meta = safe_dict(getattr(world_state, 'meta', {}))
        meta_updates['economic_feedback_history'] = append_unique_history(list(meta.get('economic_feedback_history') or []), economic_feedback, key_fields=('event_id',), limit=100)
        meta_updates['economic_roi_history'] = append_unique_history(list(meta.get('economic_roi_history') or []), roi_history, key_fields=('event_id',), limit=100)
        meta_updates['economic_policy_snapshot_history'] = append_unique_history(list(meta.get('economic_policy_snapshot_history') or []), policy_snapshot, key_fields=('snapshot_id',), limit=100)
        meta.update(meta_updates)
        try:
            setattr(world_state, 'meta', meta)
            return world_state
        except Exception:
            pass
        dataclass_fields = getattr(world_state, '__dataclass_fields__', None)
        if dataclass_fields and 'meta' in dataclass_fields:
            return replace(world_state, meta=meta)
        state_copy = getattr(world_state, '__dict__', None)
        if isinstance(state_copy, dict):
            cloned = dict(state_copy)
            cloned['meta'] = meta
            return cloned
    return world_state
