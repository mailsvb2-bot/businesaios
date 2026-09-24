from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from governance.persistence_codec import atomic_write_json, exclusive_file_lock
from shared.runtime_paths import shared_runtime_root

from runtime.state.business_fact_lifecycle import apply_business_fact_supersession
from runtime.state.state_contract import (
    StateConflictRecord,
    StateEvidenceRef,
    StateFieldRecord,
    StateObservation,
    StateSynthesizedSnapshot,
)
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES, StateFreshnessPolicy
from runtime.state.state_identity import build_state_id
from runtime.state.state_provenance import provenance_hash, provenance_payload, validate_record_provenance
from runtime.state.state_unknown_semantics import classify_value_kind
from runtime.state.state_value_projection import materialize_state_values
from runtime.state.world_model_semantic_projector import project_world_model_semantics

CANON_STATE_SNAPSHOT_STORE = True


def canonical_state_snapshot_root(*, root_dir: str | Path | None = None) -> Path:
    """Return the one durable semantic-state root shared by runtime surfaces."""

    root = Path(root_dir) if root_dir is not None else (shared_runtime_root() or Path(".runtime"))
    return root / "runtime" / "state"


def build_canonical_state_synthesis_engine(*, root_dir: str | Path | None = None):
    """Build the existing StateSynthesisEngine over the canonical snapshot store."""

    from runtime.state.state_synthesis_engine import StateSynthesisEngine

    return StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(canonical_state_snapshot_root(root_dir=root_dir))
    )


def _recompute_current_record_freshness(
    record: StateFieldRecord,
    *,
    envelope: dict[str, Any],
    tenant_id: str,
    business_id: str,
    now_ms: int,
) -> StateFieldRecord:
    original_meta = envelope.get("meta")
    if not isinstance(original_meta, dict):
        raise ValueError(f"state record provenance envelope meta is invalid: {record.field_path}")
    observation = StateObservation(
        field_path=str(envelope.get("field_path") or record.field_path),
        value=envelope.get("value"),
        source=str(envelope.get("source") or record.source),
        observed_at_ms=int(envelope.get("observed_at_ms") or 0),
        recorded_at_ms=int(envelope.get("recorded_at_ms") or envelope.get("observed_at_ms") or 0),
        occurred_at_ms=None if envelope.get("occurred_at_ms") is None else int(envelope["occurred_at_ms"]),
        valid_from_ms=None if envelope.get("valid_from_ms") is None else int(envelope["valid_from_ms"]),
        valid_until_ms=None if envelope.get("valid_until_ms") is None else int(envelope["valid_until_ms"]),
        superseded_at_ms=None if envelope.get("superseded_at_ms") is None else int(envelope["superseded_at_ms"]),
        confidence=float(envelope.get("confidence") if envelope.get("confidence") is not None else record.confidence),
        source_priority=int(envelope.get("source_priority") or 0),
        authoritative=bool(envelope.get("authoritative")),
        ttl_ms=None if envelope.get("ttl_ms") is None else int(envelope["ttl_ms"]),
        unknown=bool(envelope.get("unknown")),
        absent=bool(envelope.get("absent")),
        evidence_refs=tuple(record.evidence_refs),
        semantic_kind=str(envelope.get("semantic_kind") or record.semantic_kind),
        meta=dict(original_meta),
        tenant_id=tenant_id,
        business_id=business_id,
    )
    freshness = StateFreshnessPolicy().evaluate(now_ms=int(now_ms), observation=observation)
    meta = dict(record.meta)
    meta["effective_ttl_ms"] = freshness.effective_ttl_ms
    meta["age_ms"] = freshness.age_ms
    return replace(
        record,
        value_kind=classify_value_kind(
            value=record.value,
            unknown=bool(envelope.get("unknown")),
            absent=bool(envelope.get("absent")),
            stale=freshness.status in NON_DECISION_FRESHNESS_STATUSES or freshness.status == "stale",
            conflict=bool(record.conflict),
        ),
        freshness_status=freshness.status,
        freshness_reason=freshness.reason,
        superseded_at_ms=observation.superseded_at_ms,
        meta=meta,
    )


def _validate_current_conflict_consistency(
    conflict: StateConflictRecord,
    field: StateFieldRecord,
) -> None:
    field_status = str(field.meta.get("conflict_status") or "")
    field_policy = str(field.meta.get("resolution_policy") or "")
    if conflict.status == "resolved":
        if field.conflict or field_status != "resolved":
            raise ValueError(f"current state resolved conflict field mismatch: {conflict.field_path}")
        if str(field.meta.get("resolved_conflict_id") or "") != conflict.conflict_id:
            raise ValueError(f"current state resolved conflict identity mismatch: {conflict.field_path}")
        if field_policy != conflict.resolution_policy:
            raise ValueError(f"current state resolved conflict policy mismatch: {conflict.field_path}")
        if conflict.resolution_policy != "human_evidence_bound_resolution@v1":
            raise ValueError(f"current state resolved conflict policy is invalid: {conflict.field_path}")
        field_evidence = tuple(str(item) for item in field.meta.get("resolution_evidence_refs") or ())
        if field_evidence != tuple(conflict.resolution_evidence_refs):
            raise ValueError(f"current state resolved conflict evidence mismatch: {conflict.field_path}")
        if not str(field.meta.get("resolved_by") or "").strip():
            raise ValueError(f"current state resolved conflict actor is missing: {conflict.field_path}")
        if int(field.meta.get("resolved_at_ms") or -1) < int(conflict.detected_at_ms):
            raise ValueError(f"current state resolved conflict timestamp is invalid: {conflict.field_path}")
        return
    if not field.conflict or field_status != conflict.status:
        raise ValueError(f"current state conflict status mismatch: {conflict.field_path}")
    if field_policy != conflict.resolution_policy:
        raise ValueError(f"current state conflict policy mismatch: {conflict.field_path}")
    if field.meta.get("resolved_conflict_id"):
        raise ValueError(f"current state unresolved conflict carries resolution identity: {conflict.field_path}")


@dataclass
class FileStateSnapshotStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def load_latest(self, *, tenant_id: str, business_id: str) -> StateSynthesizedSnapshot | None:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return None
        return snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_snapshot(self, snapshot: StateSynthesizedSnapshot) -> None:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id)
        with exclusive_file_lock(path):
            atomic_write_json(path, snapshot.to_dict())

    def save_snapshot_if_current(
        self,
        snapshot: StateSynthesizedSnapshot,
        *,
        expected_state_id: str | None,
    ) -> None:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id)
        with exclusive_file_lock(path):
            current = (
                snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))
                if path.exists()
                else None
            )
            current_state_id = None if current is None else current.state_id
            expected = None if expected_state_id is None else str(expected_state_id)
            if current_state_id != expected:
                raise RuntimeError("STATE_SNAPSHOT_CONCURRENT_UPDATE")
            atomic_write_json(path, snapshot.to_dict())

    def _path(self, *, tenant_id: str, business_id: str) -> Path:
        return self.root_dir / str(tenant_id) / f"{business_id}.json"


def snapshot_from_dict(
    payload: dict[str, Any], *, allow_legacy_migration: bool = False
) -> StateSynthesizedSnapshot:
    tenant_id = str(payload.get("tenant_id") or "")
    business_id = str(payload.get("business_id") or "")
    synthesized_at_ms = int(payload.get("synthesized_at_ms") or 0)
    schema_version = str(payload.get("schema_version") or "state_synthesis@v1")
    if schema_version not in {"state_synthesis@v1", "state_synthesis@v2"}:
        raise ValueError(f"unsupported state snapshot schema_version: {schema_version}")
    legacy_schema = schema_version == "state_synthesis@v1"
    fields: dict[str, StateFieldRecord] = {}
    migrated_hashes: dict[tuple[str, str], str] = {}
    for key, value in dict(payload.get("fields") or {}).items():
        field_path = str(key)
        record_field_path = str(value.get("field_path") or "")
        if field_path != record_field_path:
            raise ValueError(f"state field map key mismatch: key={field_path} record={record_field_path}")
        evidence_refs = tuple(
            StateEvidenceRef(
                evidence_id=str(item.get("evidence_id") or ""),
                kind=str(item.get("kind") or "external"),
                uri=str(item.get("uri") or ""),
                checksum=str(item.get("checksum") or ""),
                observed_at_ms=int(item.get("observed_at_ms") or 0),
                meta=dict(item.get("meta") or {}),
            )
            for item in value.get("evidence_refs") or []
        )
        original_hash = str(value.get("provenance_hash") or "")
        envelope = dict(value.get("provenance_envelope") or {})
        record = StateFieldRecord(
            field_path=str(value["field_path"]),
            value=value.get("value"),
            value_kind=str(value.get("value_kind") or "known"),
            source=str(value.get("source") or ""),
            observed_at_ms=int(value.get("observed_at_ms") or 0),
            recorded_at_ms=int(value.get("recorded_at_ms") or value.get("observed_at_ms") or 0),
            freshness_status=str(value.get("freshness_status") or "fresh"),
            freshness_reason=str(value.get("freshness_reason") or ""),
            confidence=float(value.get("confidence") if value.get("confidence") is not None else 0.0),
            source_priority=int(value.get("source_priority") or 0),
            authoritative=bool(value.get("authoritative")),
            provenance_hash=original_hash,
            semantic_kind=str(value.get("semantic_kind") or "state"),
            occurred_at_ms=None if value.get("occurred_at_ms") is None else int(value["occurred_at_ms"]),
            valid_from_ms=None if value.get("valid_from_ms") is None else int(value["valid_from_ms"]),
            valid_until_ms=None if value.get("valid_until_ms") is None else int(value["valid_until_ms"]),
            superseded_at_ms=None if value.get("superseded_at_ms") is None else int(value["superseded_at_ms"]),
            evidence_refs=evidence_refs,
            candidates_considered=int(value.get("candidates_considered") or 1),
            conflict=bool(value.get("conflict")),
            provenance_envelope=envelope,
            meta=dict(value.get("meta") or {}),
        )
        if not envelope:
            if not legacy_schema:
                raise ValueError(f"current state snapshot is missing provenance envelope: {field_path}")
            if not allow_legacy_migration:
                raise ValueError(
                    f"legacy state snapshot requires explicit trusted migration: {field_path}"
                )
            migration_observation = StateObservation(
                field_path=record.field_path,
                value=record.value,
                source=record.source,
                observed_at_ms=record.observed_at_ms,
                recorded_at_ms=record.recorded_at_ms,
                occurred_at_ms=record.occurred_at_ms,
                valid_from_ms=record.valid_from_ms,
                valid_until_ms=record.valid_until_ms,
                superseded_at_ms=record.superseded_at_ms,
                confidence=record.confidence,
                source_priority=record.source_priority,
                authoritative=record.authoritative,
                ttl_ms=record.meta.get("effective_ttl_ms"),
                unknown=record.value_kind == "unknown",
                absent=record.value_kind == "absent",
                evidence_refs=record.evidence_refs,
                semantic_kind=record.semantic_kind,
                meta=dict(record.meta),
                tenant_id=tenant_id,
                business_id=business_id,
            )
            envelope = provenance_payload(
                observation=migration_observation,
                tenant_id=tenant_id,
                business_id=business_id,
            )
            migrated_hash = provenance_hash(
                observation=migration_observation,
                tenant_id=tenant_id,
                business_id=business_id,
            )
            migrated_hashes[(field_path, original_hash)] = migrated_hash
            record = StateFieldRecord(
                field_path=record.field_path,
                value=record.value,
                value_kind=record.value_kind,
                source=record.source,
                observed_at_ms=record.observed_at_ms,
                recorded_at_ms=record.recorded_at_ms,
                freshness_status=record.freshness_status,
                freshness_reason=record.freshness_reason,
                confidence=record.confidence,
                source_priority=record.source_priority,
                authoritative=record.authoritative,
                provenance_hash=migrated_hash,
                evidence_refs=record.evidence_refs,
                occurred_at_ms=record.occurred_at_ms,
                valid_from_ms=record.valid_from_ms,
                valid_until_ms=record.valid_until_ms,
                superseded_at_ms=record.superseded_at_ms,
                semantic_kind=record.semantic_kind,
                candidates_considered=record.candidates_considered,
                conflict=record.conflict,
                provenance_envelope=envelope,
                meta={**dict(record.meta), "legacy_provenance_rekeyed_from": original_hash},
            )
        else:
            validate_record_provenance(record=record, tenant_id=tenant_id, business_id=business_id)
            record = _recompute_current_record_freshness(
                record,
                envelope=envelope,
                tenant_id=tenant_id,
                business_id=business_id,
                now_ms=synthesized_at_ms,
            )
        fields[field_path] = record

    if not legacy_schema:
        fields = apply_business_fact_supersession(
            fields=fields,
            now_ms=synthesized_at_ms,
            tenant_id=tenant_id,
            business_id=business_id,
            freshness_policy=StateFreshnessPolicy(),
        )

    conflicts = []
    for item in payload.get("conflicts") or []:
        field_path = str(item.get("field_path") or "")
        chosen_hash = str(item.get("chosen_provenance_hash") or "")
        migrated_chosen = migrated_hashes.get((field_path, chosen_hash), chosen_hash)
        original_candidate_hashes = tuple(str(x) for x in item.get("candidate_provenance_hashes") or ())
        candidate_hashes = tuple(
            migrated_hashes.get((field_path, value), value) for value in original_candidate_hashes
        )
        conflict_id = str(item.get("conflict_id") or "")
        conflict_tenant_id = str(item.get("tenant_id") or tenant_id)
        conflict_business_id = str(item.get("business_id") or business_id)
        candidate_sources = tuple(str(x) for x in item.get("candidate_sources") or ())
        chosen_source = str(item.get("chosen_source") or "")
        if not legacy_schema:
            if not conflict_id:
                raise ValueError(f"current state conflict_id is required: {field_path}")
            if conflict_tenant_id != tenant_id or conflict_business_id != business_id:
                raise ValueError(f"current state conflict scope mismatch: {field_path}")
            if field_path not in fields:
                raise ValueError(f"current state conflict field is missing: {field_path}")
            if not candidate_hashes or migrated_chosen not in candidate_hashes:
                raise ValueError(f"current state conflict candidate hashes are invalid: {field_path}")
            if len(candidate_sources) != len(candidate_hashes) or chosen_source not in candidate_sources:
                raise ValueError(f"current state conflict candidate sources are invalid: {field_path}")
        elif migrated_chosen != chosen_hash or candidate_hashes != original_candidate_hashes:
            conflict_id = ""
        conflict_record = StateConflictRecord(
                field_path=field_path,
                tenant_id=conflict_tenant_id,
                business_id=conflict_business_id,
                chosen_source=chosen_source,
                chosen_provenance_hash=migrated_chosen,
                candidate_sources=candidate_sources,
                candidate_provenance_hashes=candidate_hashes,
                conflict_id=(conflict_id if not legacy_schema or (item.get("tenant_id") and item.get("business_id")) else ""),
                reason=str(item.get("reason") or ""),
                conflict_kind=str(item.get("conflict_kind") or "multi_source"),
                detected_at_ms=int(item.get("detected_at_ms") or 0),
                status=str(item.get("status") or "auto_resolved"),
                resolution_policy=str(item.get("resolution_policy") or "ranked_state_conflict_policy@v1"),
                resolution_evidence_refs=tuple(str(x) for x in item.get("resolution_evidence_refs") or ()),
            )
        if not legacy_schema:
            _validate_current_conflict_consistency(conflict_record, fields[field_path])
        conflicts.append(conflict_record)

    if not legacy_schema:
        expected_state_id = build_state_id(
            tenant_id=tenant_id,
            business_id=business_id,
            now_ms=synthesized_at_ms,
            fields=fields,
            conflicts=tuple(conflicts),
        )
        if str(payload.get("state_id") or "") != expected_state_id:
            raise ValueError("current state snapshot identity mismatch")

    snapshot = StateSynthesizedSnapshot(
        state_id=str(payload.get("state_id") or ""),
        tenant_id=tenant_id,
        business_id=business_id,
        synthesized_at_ms=synthesized_at_ms,
        schema_version=("state_synthesis@v2" if legacy_schema else schema_version),
        values=materialize_state_values(fields),
        fields=fields,
        conflicts=tuple(conflicts),
        source_watermarks={str(key): int(value) for key, value in dict(payload.get("source_watermarks") or {}).items()},
        audit=dict(payload.get("audit") or {}),
        meta=dict(payload.get("meta") or {}),
        semantic_view=None,
    )
    if legacy_schema:
        return snapshot
    return replace(snapshot, semantic_view=project_world_model_semantics(snapshot))

def migrate_legacy_snapshot_from_dict(payload: dict[str, Any]) -> StateSynthesizedSnapshot:
    if str(payload.get("schema_version") or "state_synthesis@v1") != "state_synthesis@v1":
        raise ValueError("legacy migration accepts only state_synthesis@v1 snapshots")
    return snapshot_from_dict(payload, allow_legacy_migration=True)
