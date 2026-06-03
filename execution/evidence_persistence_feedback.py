from __future__ import annotations

import hashlib
import json
from typing import Any
from collections.abc import Mapping, MutableMapping

from application.effects.canonical_execution_feedback import canonical_execution_feedback, canonical_persisted_outcome

CANON_EVIDENCE_PERSISTENCE_FEEDBACK = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _ensure_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, MutableMapping):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or '').strip()


def refs_from_verification(verification_result: Mapping[str, Any] | None) -> list[str]:
    payload = _safe_dict(verification_result)
    verification = _safe_dict(payload.get('verification'))
    evidence_bundle = _safe_dict(payload.get('evidence_bundle'))
    refs = verification.get('external_refs') or evidence_bundle.get('external_refs') or []
    return [str(item) for item in refs if str(item).strip()]


def compact_verification_payload(verification_result: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = canonical_execution_feedback(verification_result=verification_result)
    return canonical_persisted_outcome(snapshot)


def compact_evidence_payload(verification_result: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(verification_result)
    evidence_bundle = _safe_dict(payload.get('evidence_bundle'))
    return {
        'action_type': _text(evidence_bundle.get('action_type')),
        'action_id': _text(evidence_bundle.get('action_id')),
        'external_refs': list(evidence_bundle.get('external_refs') or []),
        'max_confidence': evidence_bundle.get('max_confidence'),
        'has_external_evidence': bool(evidence_bundle.get('has_external_evidence', False)),
        'records': list(evidence_bundle.get('records') or []),
    }


def stable_digest(payload: Mapping[str, Any] | None) -> str:
    raw = json.dumps(_safe_dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def persistence_key(*, tenant_id: str = '', business_id: str = '', run_id: str = '', step_index: int | None = None, outcome: Mapping[str, Any] | None = None) -> str:
    payload = {
        'tenant_id': str(tenant_id),
        'business_id': str(business_id),
        'run_id': str(run_id),
        'step_index': int(step_index or 0),
        'action_type': _text(_safe_dict(outcome).get('action_type')),
        'action_id': _text(_safe_dict(outcome).get('action_id')),
        'verification_status': _text(_safe_dict(outcome).get('verification_status') or _safe_dict(outcome).get('status')),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    'CANON_EVIDENCE_PERSISTENCE_FEEDBACK',
    'compact_evidence_payload',
    'compact_verification_payload',
    'persistence_key',
    'refs_from_verification',
    'stable_digest',
]
