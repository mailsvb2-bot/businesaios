from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from contracts.world_model_semantics import WorldModelSemanticViewV1, normalize_world_model_semantic_kind

CANON_STATE_SYNTHESIS_CONTRACT = True
STATE_SYNTHESIS_SCHEMA_VERSION = "state_synthesis@v2"
UNKNOWN_VALUE_KIND = "unknown"
ABSENT_VALUE_KIND = "absent"
CONFLICT_VALUE_KIND = "conflict"
STALE_VALUE_KIND = "stale"
STATE_CONFLICT_STATUSES = ("open", "auto_resolved", "human_required", "resolved")


@dataclass(frozen=True)
class StateEvidenceRef:
    evidence_id: str
    kind: str = "external"
    uri: str = ""
    checksum: str = ""
    observed_at_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": str(self.evidence_id),
            "kind": str(self.kind),
            "uri": str(self.uri),
            "checksum": str(self.checksum),
            "observed_at_ms": int(self.observed_at_ms),
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class StateObservation:
    field_path: str
    value: Any
    source: str
    observed_at_ms: int
    recorded_at_ms: int | None = None
    confidence: float = 1.0
    source_priority: int = 100
    authoritative: bool = False
    ttl_ms: int | None = None
    unknown: bool = False
    absent: bool = False
    evidence_refs: tuple[StateEvidenceRef, ...] = ()
    occurred_at_ms: int | None = None
    valid_from_ms: int | None = None
    valid_until_ms: int | None = None
    superseded_at_ms: int | None = None
    semantic_kind: str = "state"
    meta: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None
    business_id: str | None = None
    _trusted_provenance_hash: str = field(default="", init=False, repr=False, compare=False)
    _trusted_provenance_envelope: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)
    _trusted_business_fact_id: str = field(default="", init=False, repr=False, compare=False)
    _trusted_supersedes_fact_id: str = field(default="", init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not str(self.field_path or "").strip():
            raise ValueError("field_path is required")
        if not str(self.source or "").strip():
            raise ValueError("source is required")
        if int(self.observed_at_ms) < 0:
            raise ValueError("observed_at_ms must be >= 0")
        if self.recorded_at_ms is not None and int(self.recorded_at_ms) < 0:
            raise ValueError("recorded_at_ms must be >= 0")
        for name in ("occurred_at_ms", "valid_from_ms", "valid_until_ms", "superseded_at_ms"):
            value = getattr(self, name)
            if value is not None and int(value) < 0:
                raise ValueError(f"{name} must be >= 0")
        if (
            self.valid_from_ms is not None
            and self.valid_until_ms is not None
            and int(self.valid_until_ms) < int(self.valid_from_ms)
        ):
            raise ValueError("valid_until_ms must not precede valid_from_ms")
        if (
            self.superseded_at_ms is not None
            and self.valid_from_ms is not None
            and int(self.superseded_at_ms) < int(self.valid_from_ms)
        ):
            raise ValueError("superseded_at_ms must not precede valid_from_ms")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.ttl_ms is not None and int(self.ttl_ms) < 0:
            raise ValueError("ttl_ms must be >= 0")
        if bool(self.unknown) and bool(self.absent):
            raise ValueError("unknown and absent cannot both be true")
        for scope_name in ("tenant_id", "business_id"):
            scope_value = getattr(self, scope_name)
            if scope_value is None:
                continue
            normalized_scope = str(scope_value).strip()
            if not normalized_scope:
                raise ValueError(f"{scope_name} must not be empty when provided")
            object.__setattr__(self, scope_name, normalized_scope)
        object.__setattr__(self, "semantic_kind", normalize_world_model_semantic_kind(self.semantic_kind))

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": str(self.field_path),
            "value": self.value,
            "source": str(self.source),
            "observed_at_ms": int(self.observed_at_ms),
            "recorded_at_ms": None if self.recorded_at_ms is None else int(self.recorded_at_ms),
            "occurred_at_ms": None if self.occurred_at_ms is None else int(self.occurred_at_ms),
            "valid_from_ms": None if self.valid_from_ms is None else int(self.valid_from_ms),
            "valid_until_ms": None if self.valid_until_ms is None else int(self.valid_until_ms),
            "superseded_at_ms": None if self.superseded_at_ms is None else int(self.superseded_at_ms),
            "confidence": float(self.confidence),
            "source_priority": int(self.source_priority),
            "authoritative": bool(self.authoritative),
            "ttl_ms": None if self.ttl_ms is None else int(self.ttl_ms),
            "unknown": bool(self.unknown),
            "absent": bool(self.absent),
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "semantic_kind": str(self.semantic_kind),
            "meta": dict(self.meta),
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
        }


@dataclass(frozen=True)
class StateFieldRecord:
    field_path: str
    value: Any
    value_kind: str
    source: str
    observed_at_ms: int
    recorded_at_ms: int
    freshness_status: str
    freshness_reason: str
    confidence: float
    source_priority: int
    authoritative: bool
    provenance_hash: str
    evidence_refs: tuple[StateEvidenceRef, ...] = ()
    occurred_at_ms: int | None = None
    valid_from_ms: int | None = None
    valid_until_ms: int | None = None
    superseded_at_ms: int | None = None
    semantic_kind: str = "state"
    candidates_considered: int = 1
    conflict: bool = False
    provenance_envelope: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.field_path or "").strip():
            raise ValueError("field_path is required")
        if not str(self.source or "").strip():
            raise ValueError("source is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        for name in ("occurred_at_ms", "valid_from_ms", "valid_until_ms", "superseded_at_ms"):
            value = getattr(self, name)
            if value is not None and int(value) < 0:
                raise ValueError(f"{name} must be >= 0")
        if (
            self.valid_from_ms is not None
            and self.valid_until_ms is not None
            and int(self.valid_until_ms) < int(self.valid_from_ms)
        ):
            raise ValueError("valid_until_ms must not precede valid_from_ms")
        object.__setattr__(self, "semantic_kind", normalize_world_model_semantic_kind(self.semantic_kind))

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": str(self.field_path),
            "value": self.value,
            "value_kind": str(self.value_kind),
            "source": str(self.source),
            "observed_at_ms": int(self.observed_at_ms),
            "recorded_at_ms": int(self.recorded_at_ms),
            "freshness_status": str(self.freshness_status),
            "freshness_reason": str(self.freshness_reason),
            "confidence": float(self.confidence),
            "source_priority": int(self.source_priority),
            "authoritative": bool(self.authoritative),
            "provenance_hash": str(self.provenance_hash),
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "occurred_at_ms": None if self.occurred_at_ms is None else int(self.occurred_at_ms),
            "valid_from_ms": None if self.valid_from_ms is None else int(self.valid_from_ms),
            "valid_until_ms": None if self.valid_until_ms is None else int(self.valid_until_ms),
            "superseded_at_ms": None if self.superseded_at_ms is None else int(self.superseded_at_ms),
            "semantic_kind": str(self.semantic_kind),
            "candidates_considered": int(self.candidates_considered),
            "conflict": bool(self.conflict),
            "provenance_envelope": dict(self.provenance_envelope),
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class StateConflictRecord:
    field_path: str
    tenant_id: str
    business_id: str
    chosen_source: str
    chosen_provenance_hash: str
    candidate_sources: tuple[str, ...]
    reason: str
    conflict_kind: str = "multi_source"
    detected_at_ms: int = 0
    status: str = "auto_resolved"
    resolution_policy: str = "ranked_state_conflict_policy@v1"
    resolution_evidence_refs: tuple[str, ...] = ()
    candidate_provenance_hashes: tuple[str, ...] = ()
    conflict_id: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATE_CONFLICT_STATUSES:
            raise ValueError(f"unsupported conflict status: {self.status}")
        if not str(self.field_path or "").strip():
            raise ValueError("field_path is required")
        for scope_name in ("tenant_id", "business_id"):
            scope_value = str(getattr(self, scope_name) or "").strip()
            if not scope_value:
                raise ValueError(f"{scope_name} is required for conflict identity")
            object.__setattr__(self, scope_name, scope_value)
        if int(self.detected_at_ms) < 0:
            raise ValueError("detected_at_ms must be >= 0")
        identity_hashes = tuple(str(item) for item in self.candidate_provenance_hashes)
        if not identity_hashes and self.chosen_provenance_hash:
            identity_hashes = (str(self.chosen_provenance_hash),)
        payload = {
            "field_path": str(self.field_path),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "conflict_kind": str(self.conflict_kind),
            "candidate_sources": sorted(str(item) for item in self.candidate_sources),
            "candidate_provenance_hashes": sorted(identity_hashes),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected_conflict_id = hashlib.sha256(encoded).hexdigest()[:24]
        if self.conflict_id and str(self.conflict_id) != expected_conflict_id:
            raise ValueError("conflict_id does not match conflict candidate identity")
        object.__setattr__(self, "conflict_id", expected_conflict_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": str(self.conflict_id),
            "field_path": str(self.field_path),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "chosen_source": str(self.chosen_source),
            "chosen_provenance_hash": str(self.chosen_provenance_hash),
            "candidate_sources": [str(item) for item in self.candidate_sources],
            "candidate_provenance_hashes": [str(item) for item in self.candidate_provenance_hashes],
            "reason": str(self.reason),
            "conflict_kind": str(self.conflict_kind),
            "detected_at_ms": int(self.detected_at_ms),
            "status": str(self.status),
            "resolution_policy": str(self.resolution_policy),
            "resolution_evidence_refs": [str(item) for item in self.resolution_evidence_refs],
        }


@dataclass(frozen=True)
class StateConflictResolution:
    field_path: str
    conflict_id: str
    selected_provenance_hash: str
    resolved_by: str
    resolved_at_ms: int
    evidence_refs: tuple[StateEvidenceRef, ...]
    reason: str = ""

    def __post_init__(self) -> None:
        for name in ("field_path", "conflict_id", "selected_provenance_hash", "resolved_by"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} is required")
        if int(self.resolved_at_ms) < 0:
            raise ValueError("resolved_at_ms must be >= 0")
        if not self.evidence_refs:
            raise ValueError("human conflict resolution requires evidence_refs")
        if any(not (item.evidence_id or item.uri or item.checksum) for item in self.evidence_refs):
            raise ValueError("each conflict resolution evidence ref requires an identity")
        if any(int(item.observed_at_ms) > int(self.resolved_at_ms) for item in self.evidence_refs):
            raise ValueError("conflict resolution evidence must not postdate resolved_at_ms")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": str(self.field_path),
            "conflict_id": str(self.conflict_id),
            "selected_provenance_hash": str(self.selected_provenance_hash),
            "resolved_by": str(self.resolved_by),
            "resolved_at_ms": int(self.resolved_at_ms),
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "reason": str(self.reason),
        }


@dataclass(frozen=True)
class StateSynthesizedSnapshot:
    state_id: str
    tenant_id: str
    business_id: str
    synthesized_at_ms: int
    schema_version: str = STATE_SYNTHESIS_SCHEMA_VERSION
    values: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, StateFieldRecord] = field(default_factory=dict)
    conflicts: tuple[StateConflictRecord, ...] = ()
    source_watermarks: dict[str, int] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    semantic_view: WorldModelSemanticViewV1 | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": str(self.state_id),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "synthesized_at_ms": int(self.synthesized_at_ms),
            "schema_version": str(self.schema_version),
            "values": dict(self.values),
            "fields": {key: value.to_dict() for key, value in self.fields.items()},
            "conflicts": [item.to_dict() for item in self.conflicts],
            "source_watermarks": {str(key): int(value) for key, value in self.source_watermarks.items()},
            "audit": dict(self.audit),
            "meta": dict(self.meta),
            "semantic_view": None if self.semantic_view is None else self.semantic_view.as_dict(),
        }


@dataclass(frozen=True)
class StateSynthesisRequest:
    tenant_id: str
    business_id: str
    now_ms: int
    observations: tuple[StateObservation, ...]
    base_snapshot: StateSynthesizedSnapshot | None = None
    conflict_resolutions: tuple[StateConflictResolution, ...] = ()
    correlation_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if int(self.now_ms) < 0:
            raise ValueError("now_ms must be >= 0")
        if self.base_snapshot is not None:
            if str(self.base_snapshot.tenant_id) != str(self.tenant_id):
                raise ValueError("base_snapshot tenant_id mismatch")
            if str(self.base_snapshot.business_id) != str(self.business_id):
                raise ValueError("base_snapshot business_id mismatch")
        for observation in self.observations:
            if observation._trusted_provenance_hash:
                raise ValueError("trusted provenance is reserved for internal snapshot rehydration")
            if "inherited_provenance_hash" in observation.meta:
                raise ValueError("inherited_provenance_hash is reserved for internal snapshot rehydration")
            reserved_business_fact_meta = {
                "business_fact_id",
                "business_fact_subject",
                "business_fact_provenance",
                "business_fact_supersedes_fact_id",
                "superseded_by_business_fact_id",
                "business_fact_pre_supersession_lifecycle",
            } & set(observation.meta)
            if reserved_business_fact_meta and not observation._trusted_business_fact_id:
                raise ValueError("business_fact metadata is reserved for canonical BusinessFact projection")
            if observation._trusted_business_fact_id:
                if str(observation.meta.get("business_fact_id") or "") != observation._trusted_business_fact_id:
                    raise ValueError("trusted BusinessFact identity mismatch")
                if observation.semantic_kind != "fact":
                    raise ValueError("trusted BusinessFact observation must use fact epistemic type")
                if not isinstance(observation.value, dict):
                    raise ValueError("trusted BusinessFact observation requires a mapping value")
                value_supersedes = str(observation.value.get("supersedes_fact_id") or "")
                if value_supersedes != str(observation._trusted_supersedes_fact_id or ""):
                    raise ValueError("trusted BusinessFact supersession mismatch")
            if observation.tenant_id is not None and str(observation.tenant_id) != str(self.tenant_id):
                raise ValueError("observation tenant_id mismatch")
            if observation.business_id is not None and str(observation.business_id) != str(self.business_id):
                raise ValueError("observation business_id mismatch")
        resolution_paths: set[str] = set()
        for resolution in self.conflict_resolutions:
            if resolution.field_path in resolution_paths:
                raise ValueError(f"duplicate conflict resolution for field_path: {resolution.field_path}")
            resolution_paths.add(resolution.field_path)
            if int(resolution.resolved_at_ms) > int(self.now_ms):
                raise ValueError("resolved_at_ms must not be in the future")


class StateSnapshotStorePort(Protocol):
    def load_latest(self, *, tenant_id: str, business_id: str) -> StateSynthesizedSnapshot | None: ...

    def save_snapshot(self, snapshot: StateSynthesizedSnapshot) -> None: ...


class StateDeltaLogPort(Protocol):
    def append(self, *, previous: StateSynthesizedSnapshot | None, current: StateSynthesizedSnapshot) -> None: ...


class StateAuditTrailPort(Protocol):
    def record(self, *, request: StateSynthesisRequest, snapshot: StateSynthesizedSnapshot) -> None: ...
