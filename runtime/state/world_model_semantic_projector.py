from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from contracts.event_store import BusinessFactV1
from contracts.world_model_semantics import (
    WorldModelSemanticRecordV1,
    WorldModelSemanticViewV1,
    normalize_world_model_semantic_kind,
)
from runtime.state.business_fact_lifecycle import bind_trusted_business_fact, business_fact_field_path
from runtime.state.state_contract import StateEvidenceRef, StateObservation, StateSynthesizedSnapshot
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES

CANON_WORLD_MODEL_SEMANTIC_PROJECTOR = True
WORLD_MODEL_SEMANTIC_PROJECTOR_DOES_NOT_OWN_STATE = True


def project_world_model_semantics(snapshot: StateSynthesizedSnapshot) -> WorldModelSemanticViewV1:
    records: list[WorldModelSemanticRecordV1] = []
    for field_path, field in sorted(snapshot.fields.items()):
        if field.freshness_status in NON_DECISION_FRESHNESS_STATUSES:
            continue
        ttl = field.meta.get("effective_ttl_ms")
        freshness_bounds = []
        if ttl is not None:
            freshness_bounds.append(int(field.observed_at_ms) + int(ttl))
        if field.valid_until_ms is not None:
            freshness_bounds.append(int(field.valid_until_ms))
        if field.superseded_at_ms is not None:
            freshness_bounds.append(int(field.superseded_at_ms))
        fresh_until_ms = min(freshness_bounds) if freshness_bounds else None
        occurred_at_ms = int(field.occurred_at_ms if field.occurred_at_ms is not None else field.observed_at_ms)
        provenance = str(field.provenance_hash or "").strip()
        if not provenance:
            provenance = hashlib.sha256(
                f"{snapshot.tenant_id}|{snapshot.business_id}|{field_path}|{field.source}|{field.observed_at_ms}".encode()
            ).hexdigest()
        records.append(
            WorldModelSemanticRecordV1(
                record_id=f"wm:{provenance}",
                tenant_id=snapshot.tenant_id,
                business_id=snapshot.business_id,
                epistemic_type=field.semantic_kind,
                key=str(field_path),
                value=field.value,
                source=field.source,
                occurred_at_ms=occurred_at_ms,
                observed_at_ms=field.observed_at_ms,
                recorded_at_ms=field.recorded_at_ms,
                confidence=field.confidence,
                authoritative=field.authoritative,
                valid_from_ms=field.valid_from_ms,
                valid_until_ms=field.valid_until_ms,
                superseded_at_ms=field.superseded_at_ms,
                fresh_until_ms=fresh_until_ms,
                provenance_hash=provenance,
                evidence_refs=tuple(item.evidence_id or item.uri or item.checksum for item in field.evidence_refs),
                meta={
                    "value_kind": field.value_kind,
                    "freshness_status": field.freshness_status,
                    "freshness_reason": field.freshness_reason,
                    "source_priority": field.source_priority,
                    "conflict": field.conflict,
                    "conflict_status": field.meta.get("conflict_status"),
                    "resolution_policy": field.meta.get("resolution_policy"),
                    "candidates_considered": field.candidates_considered,
                    "observation_meta": deepcopy(field.meta),
                },
            )
        )
    return WorldModelSemanticViewV1(
        state_id=snapshot.state_id,
        tenant_id=snapshot.tenant_id,
        business_id=snapshot.business_id,
        generated_at_ms=snapshot.synthesized_at_ms,
        records=tuple(records),
    )


def business_fact_to_state_observation(fact: BusinessFactV1) -> StateObservation:
    provenance = dict(fact.provenance or {})
    confidence = float(provenance.get("confidence", 1.0))
    ttl = provenance.get("ttl_ms")
    observation = StateObservation(
        field_path=business_fact_field_path(
            fact_type=fact.fact_type,
            entity_id=fact.entity_id,
            fact_id=fact.fact_id,
        ),
        value={
            "fact_id": fact.fact_id,
            "tenant_id": fact.tenant_id,
            "business_id": fact.business_id,
            "fact_type": fact.fact_type,
            "entity_id": fact.entity_id,
            "event_time_ms": int(fact.event_time_ms),
            "payload": dict(fact.payload or {}),
            "supersedes_fact_id": fact.supersedes_fact_id,
        },
        source=fact.source,
        observed_at_ms=int(fact.observed_at_ms),
        recorded_at_ms=int(provenance.get("recorded_at_ms", fact.observed_at_ms)),
        occurred_at_ms=int(fact.event_time_ms),
        valid_from_ms=int(provenance.get("valid_from_ms", fact.event_time_ms)),
        valid_until_ms=None if provenance.get("valid_until_ms") is None else int(provenance["valid_until_ms"]),
        superseded_at_ms=None if provenance.get("superseded_at_ms") is None else int(provenance["superseded_at_ms"]),
        confidence=confidence,
        source_priority=int(provenance.get("source_priority", 100)),
        authoritative=bool(provenance.get("authoritative", False)),
        evidence_refs=tuple(
            StateEvidenceRef(
                evidence_id=evidence_id,
                kind="canonical_evidence",
                observed_at_ms=int(fact.observed_at_ms),
                meta={"business_fact_id": fact.fact_id},
            )
            for evidence_id in fact.evidence_ids
        ),
        ttl_ms=None if ttl is None else int(ttl),
        semantic_kind="fact",
        meta={
            "business_fact_id": fact.fact_id,
            "business_fact_subject": f"{fact.fact_type}:{fact.entity_id}",
            "decision_id": fact.decision_id,
            "correlation_id": fact.correlation_id,
            "business_fact_provenance": deepcopy(provenance),
        },
        tenant_id=fact.tenant_id,
        business_id=fact.business_id,
    )
    return bind_trusted_business_fact(
        observation,
        fact_id=fact.fact_id,
        supersedes_fact_id=fact.supersedes_fact_id,
    )


def semantic_observation(
    *,
    field_path: str,
    value: Any,
    source: str,
    observed_at_ms: int,
    kind: str,
    confidence: float = 1.0,
    authoritative: bool = False,
    ttl_ms: int | None = None,
    occurred_at_ms: int | None = None,
    recorded_at_ms: int | None = None,
    valid_from_ms: int | None = None,
    valid_until_ms: int | None = None,
    superseded_at_ms: int | None = None,
    source_priority: int = 100,
    evidence_refs: tuple[StateEvidenceRef, ...] = (),
    tenant_id: str | None = None,
    business_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> StateObservation:
    normalized_kind = normalize_world_model_semantic_kind(kind)
    return StateObservation(
        field_path=field_path,
        value=value,
        source=source,
        observed_at_ms=observed_at_ms,
        recorded_at_ms=recorded_at_ms,
        occurred_at_ms=occurred_at_ms,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        superseded_at_ms=superseded_at_ms,
        confidence=confidence,
        source_priority=source_priority,
        authoritative=authoritative,
        ttl_ms=ttl_ms,
        unknown=normalized_kind == "unknown",
        evidence_refs=tuple(evidence_refs),
        semantic_kind=normalized_kind,
        meta=dict(meta or {}),
        tenant_id=tenant_id,
        business_id=business_id,
    )


__all__ = [
    "CANON_WORLD_MODEL_SEMANTIC_PROJECTOR",
    "WORLD_MODEL_SEMANTIC_PROJECTOR_DOES_NOT_OWN_STATE",
    "business_fact_to_state_observation",
    "project_world_model_semantics",
    "semantic_observation",
]
