from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from runtime.state.state_contract import StateConflictRecord, StateFieldRecord

CANON_STATE_IDENTITY = True


def build_state_id(
    *,
    tenant_id: str,
    business_id: str,
    now_ms: int,
    fields: Mapping[str, StateFieldRecord],
    conflicts: Sequence[StateConflictRecord],
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "business_id": str(business_id),
        "now_ms": int(now_ms),
        "fields": {
            key: _field_identity(record)
            for key, record in sorted(fields.items())
        },
        "conflicts": [
            _conflict_identity(item)
            for item in sorted(
                conflicts,
                key=lambda value: (value.field_path, value.conflict_id, value.status),
            )
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _field_identity(record: StateFieldRecord) -> dict[str, object]:
    return {
        "provenance_hash": str(record.provenance_hash),
        "value_kind": str(record.value_kind),
        "freshness_status": str(record.freshness_status),
        "freshness_reason": str(record.freshness_reason),
        "superseded_at_ms": record.superseded_at_ms,
        "conflict": bool(record.conflict),
        "superseded_by_business_fact_id": record.meta.get("superseded_by_business_fact_id"),
        "conflict_status": record.meta.get("conflict_status"),
        "conflict_id": record.meta.get("conflict_id"),
        "resolved_conflict_id": record.meta.get("resolved_conflict_id"),
        "resolved_at_ms": record.meta.get("resolved_at_ms"),
        "resolution_policy": record.meta.get("resolution_policy"),
        "resolution_evidence_refs": record.meta.get("resolution_evidence_refs"),
    }


def _conflict_identity(record: StateConflictRecord) -> dict[str, object]:
    return {
        "conflict_id": str(record.conflict_id),
        "field_path": str(record.field_path),
        "status": str(record.status),
        "chosen_source": str(record.chosen_source),
        "chosen_provenance_hash": str(record.chosen_provenance_hash),
        "candidate_sources": [str(item) for item in record.candidate_sources],
        "candidate_provenance_hashes": [
            str(item) for item in record.candidate_provenance_hashes
        ],
        "detected_at_ms": int(record.detected_at_ms),
        "resolution_policy": str(record.resolution_policy),
        "resolution_evidence_refs": [
            str(item) for item in record.resolution_evidence_refs
        ],
    }


__all__ = ["CANON_STATE_IDENTITY", "build_state_id"]
