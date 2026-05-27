from __future__ import annotations

import hashlib
import json
from typing import Any

from runtime.state.state_contract import StateEvidenceRef, StateObservation

CANON_STATE_PROVENANCE = True


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_evidence_refs(items: tuple[StateEvidenceRef, ...] | list[StateEvidenceRef]) -> tuple[StateEvidenceRef, ...]:
    deduped: dict[str, StateEvidenceRef] = {}
    for item in items:
        key = str(item.evidence_id or item.uri or item.checksum)
        if not key:
            key = hashlib.sha256(canonical_json_bytes(item.to_dict())).hexdigest()
        deduped[key] = item

    ordered = sorted(
        deduped.values(),
        key=lambda entry: (int(entry.observed_at_ms), str(entry.kind), str(entry.evidence_id), str(entry.uri)),
    )
    return tuple(ordered)


def provenance_payload(*, observation: StateObservation) -> dict[str, Any]:
    return {
        "field_path": str(observation.field_path),
        "source": str(observation.source),
        "observed_at_ms": int(observation.observed_at_ms),
        "recorded_at_ms": int(observation.recorded_at_ms or observation.observed_at_ms),
        "confidence": float(observation.confidence),
        "source_priority": int(observation.source_priority),
        "authoritative": bool(observation.authoritative),
        "ttl_ms": None if observation.ttl_ms is None else int(observation.ttl_ms),
        "unknown": bool(observation.unknown),
        "absent": bool(observation.absent),
        "value": observation.value,
        "evidence_refs": [evidence.to_dict() for evidence in normalize_evidence_refs(observation.evidence_refs)],
        "meta": dict(observation.meta),
    }


def provenance_hash(*, observation: StateObservation) -> str:
    return hashlib.sha256(canonical_json_bytes(provenance_payload(observation=observation))).hexdigest()


def merge_evidence_refs(*, left: tuple[StateEvidenceRef, ...], right: tuple[StateEvidenceRef, ...]) -> tuple[StateEvidenceRef, ...]:
    return normalize_evidence_refs(tuple(left) + tuple(right))
