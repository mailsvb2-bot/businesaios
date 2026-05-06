from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


CANON_STATE_SYNTHESIS_CONTRACT = True
STATE_SYNTHESIS_SCHEMA_VERSION = "state_synthesis@v1"
UNKNOWN_VALUE_KIND = "unknown"
ABSENT_VALUE_KIND = "absent"
CONFLICT_VALUE_KIND = "conflict"
STALE_VALUE_KIND = "stale"


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
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.field_path or "").strip():
            raise ValueError("field_path is required")
        if not str(self.source or "").strip():
            raise ValueError("source is required")
        if int(self.observed_at_ms) < 0:
            raise ValueError("observed_at_ms must be >= 0")
        if self.recorded_at_ms is not None and int(self.recorded_at_ms) < 0:
            raise ValueError("recorded_at_ms must be >= 0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.ttl_ms is not None and int(self.ttl_ms) < 0:
            raise ValueError("ttl_ms must be >= 0")
        if bool(self.unknown) and bool(self.absent):
            raise ValueError("unknown and absent cannot both be true")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": str(self.field_path),
            "value": self.value,
            "source": str(self.source),
            "observed_at_ms": int(self.observed_at_ms),
            "recorded_at_ms": None if self.recorded_at_ms is None else int(self.recorded_at_ms),
            "confidence": float(self.confidence),
            "source_priority": int(self.source_priority),
            "authoritative": bool(self.authoritative),
            "ttl_ms": None if self.ttl_ms is None else int(self.ttl_ms),
            "unknown": bool(self.unknown),
            "absent": bool(self.absent),
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "meta": dict(self.meta),
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
    candidates_considered: int = 1
    conflict: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

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
            "candidates_considered": int(self.candidates_considered),
            "conflict": bool(self.conflict),
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class StateConflictRecord:
    field_path: str
    chosen_source: str
    chosen_provenance_hash: str
    candidate_sources: tuple[str, ...]
    reason: str
    conflict_kind: str = "multi_source"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": str(self.field_path),
            "chosen_source": str(self.chosen_source),
            "chosen_provenance_hash": str(self.chosen_provenance_hash),
            "candidate_sources": [str(item) for item in self.candidate_sources],
            "reason": str(self.reason),
            "conflict_kind": str(self.conflict_kind),
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
        }


@dataclass(frozen=True)
class StateSynthesisRequest:
    tenant_id: str
    business_id: str
    now_ms: int
    observations: tuple[StateObservation, ...]
    base_snapshot: StateSynthesizedSnapshot | None = None
    correlation_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if int(self.now_ms) < 0:
            raise ValueError("now_ms must be >= 0")


class StateSnapshotStorePort(Protocol):
    def load_latest(self, *, tenant_id: str, business_id: str) -> StateSynthesizedSnapshot | None:
        ...

    def save_snapshot(self, snapshot: StateSynthesizedSnapshot) -> None:
        ...


class StateDeltaLogPort(Protocol):
    def append(self, *, previous: StateSynthesizedSnapshot | None, current: StateSynthesizedSnapshot) -> None:
        ...


class StateAuditTrailPort(Protocol):
    def record(self, *, request: StateSynthesisRequest, snapshot: StateSynthesizedSnapshot) -> None:
        ...
