from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from execution.operator_override_contract import build_operator_override_subject_fingerprint

CANON_APPROVAL_GATE_FINGERPRINT_OWNER = True

_FINGERPRINT_TRANSIENT_KEYS = frozenset({'trace_id', 'expires_at', 'approval_request_fingerprint', 'approval_fingerprint', 'request_id', 'timestamp', 'created_at', 'updated_at'})
_FINGERPRINT_EXCLUDED_PAYLOAD_KEYS = frozenset({'approval_id','approval','approval_context','approval_policy','operator_override','operator_override_id','handoff'}) | _FINGERPRINT_TRANSIENT_KEYS
_FINGERPRINT_EXCLUDED_METADATA_KEYS = frozenset({'approval_id','approval','approval_context','approval_policy','operator_override','operator_override_id','handoff','approvals'}) | _FINGERPRINT_TRANSIENT_KEYS


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


def _without_transient_keys(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _without_transient_keys(item) for key, item in value.items() if str(key) not in _FINGERPRINT_TRANSIENT_KEYS}
    if isinstance(value, (list, tuple)):
        return [_without_transient_keys(item) for item in value]
    return value


def _stable_jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _stable_jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable_jsonable(item) for item in value]
    return value


def _payload_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_stable_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _impact_summary(impact: ActionImpact) -> dict[str, object]:
    return {
        'action_name': impact.action_name,
        'category': impact.category.value,
        'cost_minor': int(impact.cost_minor),
        'publication_count': int(impact.publication_count),
        'outbound_count': int(impact.outbound_count),
        'strategic_change_count': int(impact.strategic_change_count),
        'rollback_event_count': int(impact.rollback_event_count),
        'requires_human_approval': bool(impact.requires_human_approval),
        'confidence': float(impact.confidence),
        'policy_key': getattr(impact.policy_ref, 'policy_key', None),
        'policy_version': getattr(impact.policy_ref, 'version', None),
        'dimensions': dict(impact.dimensions),
    }


def _build_subject_payload(*, ctx: ActionExecutionContext, decision_id: str, impact: ActionImpact, external_confirmation_mode: str) -> dict[str, Any]:
    payload = {str(k): _without_transient_keys(v) for k, v in _safe_dict(ctx.payload).items() if str(k) not in _FINGERPRINT_EXCLUDED_PAYLOAD_KEYS}
    metadata = {str(k): _without_transient_keys(v) for k, v in _safe_dict(ctx.metadata).items() if str(k) not in _FINGERPRINT_EXCLUDED_METADATA_KEYS}
    meta = _safe_dict(_without_transient_keys(_safe_dict(ctx.payload).get('meta') or _safe_dict(ctx.metadata)))
    return {
        'decision_id': decision_id,
        'action_name': ctx.action_name,
        'impact': _impact_summary(impact),
        'external_confirmation_mode': _text(external_confirmation_mode, default='required'),
        'payload_keys': tuple(sorted(str(key) for key in payload.keys())),
        'payload_digest': _payload_digest(payload),
        'metadata_keys': tuple(sorted(str(key) for key in metadata.keys())),
        'metadata_digest': _payload_digest(metadata),
        'metadata_tags': tuple(sorted(str(item) for item in _safe_list(meta.get('tags')) if _text(item))),
    }


def build_execution_subject_fingerprint(*, ctx: ActionExecutionContext, decision_id: str, impact: ActionImpact, external_confirmation_mode: str) -> str:
    execution_id = _text(ctx.execution_id or _safe_dict(ctx.metadata).get('execution_id'))
    if not execution_id:
        raise RuntimeError('approval_gate_requires_explicit_execution_id')
    return build_operator_override_subject_fingerprint(
        tenant_id=ctx.tenant_id,
        execution_id=execution_id,
        decision_id=decision_id,
        action_name=ctx.action_name,
        subject_payload=_build_subject_payload(ctx=ctx, decision_id=decision_id, impact=impact, external_confirmation_mode=external_confirmation_mode),
    )
