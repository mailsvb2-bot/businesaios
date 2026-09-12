from __future__ import annotations

import hashlib
import json
from typing import Any

from runtime.state.state_contract import StateEvidenceRef, StateFieldRecord, StateObservation

CANON_STATE_PROVENANCE = True


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_evidence_refs(
    items: tuple[StateEvidenceRef, ...] | list[StateEvidenceRef],
) -> tuple[StateEvidenceRef, ...]:
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


def provenance_payload(
    *,
    observation: StateObservation,
    tenant_id: str | None = None,
    business_id: str | None = None,
) -> dict[str, Any]:
    observation_tenant = observation.tenant_id
    observation_business = observation.business_id
    if observation_tenant is not None and tenant_id is not None and str(observation_tenant) != str(tenant_id):
        raise ValueError("observation tenant_id does not match provenance scope")
    if observation_business is not None and business_id is not None and str(observation_business) != str(business_id):
        raise ValueError("observation business_id does not match provenance scope")
    effective_tenant = observation_tenant if observation_tenant is not None else tenant_id
    effective_business = observation_business if observation_business is not None else business_id
    return {
        "field_path": str(observation.field_path),
        "tenant_id": effective_tenant,
        "business_id": effective_business,
        "source": str(observation.source),
        "observed_at_ms": int(observation.observed_at_ms),
        "recorded_at_ms": int(observation.recorded_at_ms or observation.observed_at_ms),
        "occurred_at_ms": None if observation.occurred_at_ms is None else int(observation.occurred_at_ms),
        "valid_from_ms": None if observation.valid_from_ms is None else int(observation.valid_from_ms),
        "valid_until_ms": None if observation.valid_until_ms is None else int(observation.valid_until_ms),
        "superseded_at_ms": None if observation.superseded_at_ms is None else int(observation.superseded_at_ms),
        "confidence": float(observation.confidence),
        "source_priority": int(observation.source_priority),
        "authoritative": bool(observation.authoritative),
        "ttl_ms": None if observation.ttl_ms is None else int(observation.ttl_ms),
        "unknown": bool(observation.unknown),
        "absent": bool(observation.absent),
        "value": observation.value,
        "evidence_refs": [evidence.to_dict() for evidence in normalize_evidence_refs(observation.evidence_refs)],
        "semantic_kind": str(observation.semantic_kind),
        "meta": dict(observation.meta),
    }


def provenance_hash(
    *,
    observation: StateObservation,
    tenant_id: str | None = None,
    business_id: str | None = None,
) -> str:
    return provenance_hash_from_payload(
        provenance_payload(
            observation=observation,
            tenant_id=tenant_id,
            business_id=business_id,
        )
    )



def provenance_hash_from_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def validate_record_provenance(
    *,
    record: StateFieldRecord,
    tenant_id: str,
    business_id: str,
) -> tuple[str, dict[str, Any]]:
    envelope = dict(record.provenance_envelope or {})
    if not envelope:
        raise ValueError(f"state record provenance envelope is missing: {record.field_path}")
    expected_hash = provenance_hash_from_payload(envelope)
    if expected_hash != str(record.provenance_hash):
        raise ValueError(f"state record provenance hash mismatch: {record.field_path}")

    expected = {
        "field_path": str(record.field_path),
        "tenant_id": str(tenant_id),
        "business_id": str(business_id),
        "source": str(record.source),
        "observed_at_ms": int(record.observed_at_ms),
        "recorded_at_ms": int(record.recorded_at_ms),
        "occurred_at_ms": None if record.occurred_at_ms is None else int(record.occurred_at_ms),
        "valid_from_ms": None if record.valid_from_ms is None else int(record.valid_from_ms),
        "valid_until_ms": None if record.valid_until_ms is None else int(record.valid_until_ms),
        "confidence": float(record.confidence),
        "source_priority": int(record.source_priority),
        "authoritative": bool(record.authoritative),
        "unknown": record.value_kind == "unknown",
        "absent": record.value_kind == "absent",
        "value": record.value,
        "evidence_refs": [item.to_dict() for item in normalize_evidence_refs(record.evidence_refs)],
        "semantic_kind": str(record.semantic_kind),
    }
    for key, value in expected.items():
        if envelope.get(key) != value:
            raise ValueError(f"state record provenance envelope mismatch for {key}: {record.field_path}")

    if not record.meta.get("superseded_by_business_fact_id"):
        expected_superseded = None if record.superseded_at_ms is None else int(record.superseded_at_ms)
        if envelope.get("superseded_at_ms") != expected_superseded:
            raise ValueError(
                f"state record provenance envelope mismatch for superseded_at_ms: {record.field_path}"
            )

    original_meta = envelope.get("meta")
    if not isinstance(original_meta, dict):
        raise ValueError(f"state record provenance envelope meta is invalid: {record.field_path}")
    for key, value in original_meta.items():
        if record.meta.get(key) != value:
            raise ValueError(f"state record provenance envelope mismatch for meta.{key}: {record.field_path}")
    return expected_hash, envelope

def merge_evidence_refs(
    *, left: tuple[StateEvidenceRef, ...], right: tuple[StateEvidenceRef, ...]
) -> tuple[StateEvidenceRef, ...]:
    return normalize_evidence_refs(tuple(left) + tuple(right))
