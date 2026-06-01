from __future__ import annotations

import json
from dataclasses import is_dataclass, replace
from datetime import UTC, datetime
from typing import Any, Mapping, MutableMapping

from execution.business_operating_memory import (
    project_business_memory_evidence,
    project_business_memory_governance_summary,
)


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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _external_refs_fingerprint(value: object) -> str:
    refs = sorted(str(item).strip() for item in list(value or []) if str(item).strip())
    return json.dumps(refs, ensure_ascii=False, separators=(',', ':'))


def apply_feedback_to_world_state(
    *,
    world_state: Any,
    compact_outcome: Mapping[str, Any],
    compact_evidence: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> Any:
    if is_dataclass(world_state) and hasattr(world_state, 'meta'):
        meta = _safe_dict(getattr(world_state, 'meta', {}))
        return replace(
            world_state,
            meta=_apply_feedback_to_meta(
                meta=meta,
                compact_outcome=compact_outcome,
                compact_evidence=compact_evidence,
                receipt=receipt,
            ),
        )
    if hasattr(world_state, 'meta'):
        patched = _apply_feedback_to_meta(
            meta=_safe_dict(getattr(world_state, 'meta', {})),
            compact_outcome=compact_outcome,
            compact_evidence=compact_evidence,
            receipt=receipt,
        )
        setattr(world_state, 'meta', patched)
        return world_state
    state = _ensure_mapping(world_state)
    state['meta'] = _apply_feedback_to_meta(
        meta=_safe_dict(state.get('meta')),
        compact_outcome=compact_outcome,
        compact_evidence=compact_evidence,
        receipt=receipt,
    )
    return state


def _apply_feedback_to_meta(
    *,
    meta: Mapping[str, Any],
    compact_outcome: Mapping[str, Any],
    compact_evidence: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    current_meta = _ensure_mapping(meta)
    memory = _ensure_mapping(current_meta.get('business_memory_evidence'))
    outcomes = [dict(item or {}) for item in memory.get('recent_outcomes') or []]
    evidences = [dict(item or {}) for item in memory.get('recent_evidence') or []]
    now_iso = _utc_now().isoformat()
    outcome_entry = {'updated_at': now_iso, **_safe_dict(compact_outcome)}
    evidence_entry = {'updated_at': now_iso, **_safe_dict(compact_evidence)}
    outcome_key = (_text(outcome_entry.get('action_type')), _text(outcome_entry.get('action_id')), _text(outcome_entry.get('status')))
    evidence_key = (_text(evidence_entry.get('action_type')), _text(evidence_entry.get('action_id')), _external_refs_fingerprint(evidence_entry.get('external_refs')))
    if all((_text(item.get('action_type')), _text(item.get('action_id')), _text(item.get('status'))) != outcome_key for item in outcomes if isinstance(item, Mapping)):
        outcomes.append(outcome_entry)
    if all((_text(item.get('action_type')), _text(item.get('action_id')), _external_refs_fingerprint(item.get('external_refs'))) != evidence_key for item in evidences if isinstance(item, Mapping)):
        evidences.append(evidence_entry)
    memory['recent_outcomes'] = outcomes[-50:]
    memory['recent_evidence'] = evidences[-50:]
    memory['last_outcome'] = outcome_entry
    memory['last_evidence'] = evidence_entry
    memory['last_persisted_at'] = now_iso
    memory['last_persistence_receipt'] = dict(receipt)
    current_meta['business_memory_evidence'] = project_business_memory_evidence(memory)
    current_meta['business_memory_summary'] = project_business_memory_governance_summary(memory)
    return current_meta


__all__ = ['apply_feedback_to_world_state']
