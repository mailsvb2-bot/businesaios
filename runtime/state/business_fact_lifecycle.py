from __future__ import annotations

import hashlib
from dataclasses import replace

from runtime.state.state_contract import StateFieldRecord, StateObservation
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES, StateFreshnessPolicy
from runtime.state.state_unknown_semantics import classify_value_kind

CANON_BUSINESS_FACT_LIFECYCLE_HELPER = True
BUSINESS_FACT_LIFECYCLE_DOES_NOT_OWN_STATE = True


def _path_component(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def business_fact_field_path(*, fact_type: str, entity_id: str, fact_id: str) -> str:
    return (
        "business.facts.by_type."
        f"{_path_component(fact_type)}.by_entity.{_path_component(entity_id)}.by_id.{_path_component(fact_id)}"
    )


def bind_trusted_business_fact(
    observation: StateObservation,
    *,
    fact_id: str,
    supersedes_fact_id: str | None,
) -> StateObservation:
    object.__setattr__(observation, "_trusted_business_fact_id", str(fact_id))
    object.__setattr__(observation, "_trusted_supersedes_fact_id", str(supersedes_fact_id or ""))
    return observation



def validate_business_fact_observation(
    observation: StateObservation,
    *,
    tenant_id: str,
    business_id: str,
) -> None:
    fact_id = str(observation._trusted_business_fact_id or "").strip()
    if not fact_id:
        return
    if observation.semantic_kind != "fact" or not isinstance(observation.value, dict):
        raise ValueError("trusted BusinessFact observation is malformed")
    if str(observation.meta.get("business_fact_id") or "") != fact_id:
        raise ValueError("trusted BusinessFact identity mismatch")
    if str(observation.value.get("fact_id") or "") != fact_id:
        raise ValueError("trusted BusinessFact payload identity mismatch")
    if str(observation.value.get("tenant_id") or "") != str(tenant_id):
        raise ValueError("trusted BusinessFact tenant scope mismatch")
    if str(observation.value.get("business_id") or "") != str(business_id):
        raise ValueError("trusted BusinessFact business scope mismatch")
    value_supersedes = str(observation.value.get("supersedes_fact_id") or "")
    if value_supersedes != str(observation._trusted_supersedes_fact_id or ""):
        raise ValueError("trusted BusinessFact supersession mismatch")


def _validated_fact_id(
    *,
    field_path: str,
    record: StateFieldRecord,
    tenant_id: str,
    business_id: str,
) -> str | None:
    fact_id = str(record.meta.get("business_fact_id") or "").strip()
    if not fact_id:
        return None
    if record.semantic_kind != "fact" or not isinstance(record.value, dict):
        raise ValueError(f"invalid durable BusinessFact record at {field_path}")
    value = record.value
    value_fact_id = str(value.get("fact_id") or "").strip()
    fact_type = str(value.get("fact_type") or "").strip()
    entity_id = str(value.get("entity_id") or "").strip()
    if not value_fact_id or value_fact_id != fact_id or not fact_type or not entity_id:
        raise ValueError(f"invalid durable BusinessFact identity at {field_path}")
    if str(value.get("tenant_id") or "") != str(tenant_id):
        raise ValueError(f"BusinessFact tenant scope mismatch at {field_path}")
    if str(value.get("business_id") or "") != str(business_id):
        raise ValueError(f"BusinessFact business scope mismatch at {field_path}")
    trusted_supersedes = str(record.meta.get("business_fact_supersedes_fact_id") or "")
    value_supersedes = str(value.get("supersedes_fact_id") or "")
    if trusted_supersedes != value_supersedes:
        raise ValueError(f"BusinessFact durable supersession mismatch at {field_path}")
    expected_path = business_fact_field_path(fact_type=fact_type, entity_id=entity_id, fact_id=fact_id)
    if str(field_path) != expected_path:
        raise ValueError(f"BusinessFact field path does not match canonical identity at {field_path}")
    return fact_id



def _restore_derived_supersession(
    record: StateFieldRecord,
    *,
    freshness_policy: StateFreshnessPolicy,
    now_ms: int,
) -> StateFieldRecord:
    successor_id = str(record.meta.get("superseded_by_business_fact_id") or "").strip()
    if not successor_id:
        return record
    envelope = dict(record.provenance_envelope or {})
    if not envelope:
        raise ValueError("derived BusinessFact supersession is missing protected provenance envelope")
    original_meta = envelope.get("meta")
    if not isinstance(original_meta, dict):
        raise ValueError("derived BusinessFact supersession provenance meta is invalid")
    original_superseded_at = envelope.get("superseded_at_ms")
    observation = StateObservation(
        field_path=str(record.field_path),
        value=record.value,
        source=str(record.source),
        observed_at_ms=int(record.observed_at_ms),
        recorded_at_ms=int(record.recorded_at_ms),
        occurred_at_ms=record.occurred_at_ms,
        valid_from_ms=record.valid_from_ms,
        valid_until_ms=record.valid_until_ms,
        superseded_at_ms=(None if original_superseded_at is None else int(original_superseded_at)),
        confidence=float(record.confidence),
        source_priority=int(record.source_priority),
        authoritative=bool(record.authoritative),
        ttl_ms=(None if envelope.get("ttl_ms") is None else int(envelope["ttl_ms"])),
        unknown=bool(envelope.get("unknown")),
        absent=bool(envelope.get("absent")),
        evidence_refs=tuple(record.evidence_refs),
        semantic_kind=str(record.semantic_kind),
        meta=dict(original_meta),
        tenant_id=str(envelope.get("tenant_id") or "") or None,
        business_id=str(envelope.get("business_id") or "") or None,
    )
    freshness = freshness_policy.evaluate(now_ms=int(now_ms), observation=observation)
    restored_meta = dict(record.meta)
    restored_meta.pop("superseded_by_business_fact_id", None)
    restored_meta.pop("business_fact_pre_supersession_lifecycle", None)
    restored_meta["effective_ttl_ms"] = freshness.effective_ttl_ms
    restored_meta["age_ms"] = freshness.age_ms
    restored_value_kind = classify_value_kind(
        value=record.value,
        unknown=bool(envelope.get("unknown")),
        absent=bool(envelope.get("absent")),
        stale=freshness.status in NON_DECISION_FRESHNESS_STATUSES,
        conflict=bool(record.conflict),
    )
    return replace(
        record,
        value_kind=restored_value_kind,
        superseded_at_ms=observation.superseded_at_ms,
        freshness_status=freshness.status,
        freshness_reason=freshness.reason,
        meta=restored_meta,
    )

def _reject_supersession_cycles(edges: dict[str, str]) -> None:
    for start in edges:
        seen: set[str] = set()
        current = start
        while current in edges:
            if current in seen:
                raise ValueError("cyclic BusinessFact supersession is forbidden")
            seen.add(current)
            current = edges[current]


def apply_business_fact_supersession(
    *,
    fields: dict[str, StateFieldRecord],
    now_ms: int,
    tenant_id: str,
    business_id: str,
    freshness_policy: StateFreshnessPolicy,
) -> dict[str, StateFieldRecord]:
    normalized_fields = {
        field_path: _restore_derived_supersession(
            record, freshness_policy=freshness_policy, now_ms=now_ms
        )
        for field_path, record in fields.items()
    }
    updated = dict(normalized_fields)
    fact_paths: dict[str, str] = {}
    for field_path, record in normalized_fields.items():
        fact_id = _validated_fact_id(
            field_path=field_path,
            record=record,
            tenant_id=tenant_id,
            business_id=business_id,
        )
        if fact_id is None:
            continue
        if fact_id in fact_paths and fact_paths[fact_id] != field_path:
            raise ValueError(f"duplicate durable BusinessFact identity: {fact_id}")
        fact_paths[fact_id] = field_path

    edges: dict[str, str] = {}
    target_to_successor: dict[str, str] = {}
    successor_records: dict[str, StateFieldRecord] = {}
    for successor_fact_id, successor_path in fact_paths.items():
        successor = normalized_fields[successor_path]
        if (
            successor.freshness_status in NON_DECISION_FRESHNESS_STATUSES
            or successor.conflict
            or successor.meta.get("conflict_status") in {"open", "human_required"}
            or not isinstance(successor.value, dict)
        ):
            continue
        superseded_fact_id = str(successor.meta.get("business_fact_supersedes_fact_id") or "").strip()
        if not superseded_fact_id:
            continue
        if successor_fact_id == superseded_fact_id:
            raise ValueError("business fact cannot supersede itself")
        if superseded_fact_id in target_to_successor and target_to_successor[superseded_fact_id] != successor_fact_id:
            raise ValueError(f"multiple active business facts supersede {superseded_fact_id}")
        target_to_successor[superseded_fact_id] = successor_fact_id
        edges[successor_fact_id] = superseded_fact_id
        successor_records[successor_fact_id] = successor

    _reject_supersession_cycles(edges)

    for successor_fact_id, superseded_fact_id in edges.items():
        target_path = fact_paths.get(superseded_fact_id)
        if target_path is None:
            continue
        successor = successor_records[successor_fact_id]
        target = updated[target_path]
        lifecycle_boundaries = [
            int(value)
            for value in (successor.occurred_at_ms, successor.valid_from_ms)
            if value is not None
        ]
        superseded_at_ms = max(lifecycle_boundaries) if lifecycle_boundaries else int(successor.observed_at_ms)
        if superseded_at_ms > int(now_ms):
            continue
        if target.valid_from_ms is not None and superseded_at_ms < int(target.valid_from_ms):
            raise ValueError(f"BusinessFact supersession predates target validity: {superseded_fact_id}")
        updated[target_path] = replace(
            target,
            superseded_at_ms=superseded_at_ms,
            freshness_status="superseded",
            freshness_reason=f"superseded_by_business_fact:{successor_fact_id}",
            meta={**dict(target.meta), "superseded_by_business_fact_id": successor_fact_id},
        )
    return updated


__all__ = [
    "BUSINESS_FACT_LIFECYCLE_DOES_NOT_OWN_STATE",
    "CANON_BUSINESS_FACT_LIFECYCLE_HELPER",
    "apply_business_fact_supersession",
    "bind_trusted_business_fact",
    "business_fact_field_path",
    "validate_business_fact_observation",
]
