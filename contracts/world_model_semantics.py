from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CANON_WORLD_MODEL_SEMANTICS_CONTRACT = True
WORLD_MODEL_SEMANTICS_SCHEMA_VERSION = "world_model_semantics@v1"
WORLD_MODEL_SEMANTIC_KINDS = (
    "fact",
    "state",
    "belief",
    "assumption",
    "goal",
    "constraint",
    "opportunity",
    "risk",
    "hypothesis",
    "forecast",
    "preference",
    "recommendation",
    "unknown",
)
_WORLD_MODEL_SEMANTIC_KIND_SET = frozenset(WORLD_MODEL_SEMANTIC_KINDS)


def normalize_world_model_semantic_kind(value: object) -> str:
    kind = str(value or "").strip().lower()
    if kind not in _WORLD_MODEL_SEMANTIC_KIND_SET:
        raise ValueError(f"unsupported world-model semantic kind: {kind or '<empty>'}")
    return kind


def _non_negative_optional(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be >= 0")
    return result


@dataclass(frozen=True)
class WorldModelSemanticRecordV1:
    record_id: str
    tenant_id: str
    business_id: str
    epistemic_type: str
    key: str
    value: Any
    source: str
    occurred_at_ms: int
    observed_at_ms: int
    recorded_at_ms: int
    confidence: float
    authoritative: bool
    provenance_hash: str
    valid_from_ms: int | None = None
    valid_until_ms: int | None = None
    superseded_at_ms: int | None = None
    fresh_until_ms: int | None = None
    evidence_refs: tuple[str, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in ("record_id", "tenant_id", "business_id", "key", "source", "provenance_hash"):
            text = str(getattr(self, name) or "")
            if not text or text.strip() != text:
                raise ValueError(f"{name} is required and must be normalized")
        object.__setattr__(self, "epistemic_type", normalize_world_model_semantic_kind(self.epistemic_type))
        for name in ("occurred_at_ms", "observed_at_ms", "recorded_at_ms"):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be >= 0")
        for name in ("valid_from_ms", "valid_until_ms", "superseded_at_ms", "fresh_until_ms"):
            object.__setattr__(self, name, _non_negative_optional(getattr(self, name), name))
        if (
            self.valid_from_ms is not None
            and self.valid_until_ms is not None
            and self.valid_until_ms < self.valid_from_ms
        ):
            raise ValueError("valid_until_ms must not precede valid_from_ms")
        if (
            self.superseded_at_ms is not None
            and self.valid_from_ms is not None
            and self.superseded_at_ms < self.valid_from_ms
        ):
            raise ValueError("superseded_at_ms must not precede valid_from_ms")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.schema_version != 1:
            raise ValueError("unsupported world-model semantic record schema")
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs if str(item).strip()))
        object.__setattr__(self, "meta", dict(self.meta or {}))

    @property
    def kind(self) -> str:
        return self.epistemic_type

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "epistemic_type": self.epistemic_type,
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "occurred_at_ms": int(self.occurred_at_ms),
            "observed_at_ms": int(self.observed_at_ms),
            "recorded_at_ms": int(self.recorded_at_ms),
            "valid_from_ms": self.valid_from_ms,
            "valid_until_ms": self.valid_until_ms,
            "superseded_at_ms": self.superseded_at_ms,
            "fresh_until_ms": self.fresh_until_ms,
            "confidence": float(self.confidence),
            "authoritative": bool(self.authoritative),
            "provenance_hash": self.provenance_hash,
            "evidence_refs": list(self.evidence_refs),
            "meta": dict(self.meta),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class WorldModelSemanticViewV1:
    state_id: str
    tenant_id: str
    business_id: str
    generated_at_ms: int
    records: tuple[WorldModelSemanticRecordV1, ...] = ()
    schema_version: str = WORLD_MODEL_SEMANTICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("state_id", "tenant_id", "business_id"):
            text = str(getattr(self, name) or "")
            if not text or text.strip() != text:
                raise ValueError(f"{name} is required and must be normalized")
        if int(self.generated_at_ms) < 0:
            raise ValueError("generated_at_ms must be >= 0")
        if self.schema_version != WORLD_MODEL_SEMANTICS_SCHEMA_VERSION:
            raise ValueError("unsupported world-model semantic view schema")
        ids = [item.record_id for item in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("world-model semantic record ids must be unique")
        for item in self.records:
            if item.tenant_id != self.tenant_id or item.business_id != self.business_id:
                raise ValueError("semantic record tenant/business identity mismatch")

    def records_for(self, epistemic_type: str) -> tuple[WorldModelSemanticRecordV1, ...]:
        normalized = normalize_world_model_semantic_kind(epistemic_type)
        return tuple(item for item in self.records if item.epistemic_type == normalized)

    def as_dict(self) -> dict[str, Any]:
        layers = {kind: [item.as_dict() for item in self.records_for(kind)] for kind in WORLD_MODEL_SEMANTIC_KINDS}
        return {
            "schema_version": self.schema_version,
            "state_id": self.state_id,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "generated_at_ms": int(self.generated_at_ms),
            "records": [item.as_dict() for item in self.records],
            "layers": layers,
        }


def world_model_semantic_record_from_dict(payload: Mapping[str, Any]) -> WorldModelSemanticRecordV1:
    data = dict(payload or {})
    observed = int(data.get("observed_at_ms") or 0)
    return WorldModelSemanticRecordV1(
        record_id=str(data.get("record_id") or ""),
        tenant_id=str(data.get("tenant_id") or ""),
        business_id=str(data.get("business_id") or ""),
        epistemic_type=str(data.get("epistemic_type") or data.get("kind") or ""),
        key=str(data.get("key") or ""),
        value=data.get("value"),
        source=str(data.get("source") or ""),
        occurred_at_ms=int(data.get("occurred_at_ms") if data.get("occurred_at_ms") is not None else observed),
        observed_at_ms=observed,
        recorded_at_ms=int(data.get("recorded_at_ms") or observed),
        valid_from_ms=None if data.get("valid_from_ms") is None else int(data["valid_from_ms"]),
        valid_until_ms=None if data.get("valid_until_ms") is None else int(data["valid_until_ms"]),
        superseded_at_ms=None if data.get("superseded_at_ms") is None else int(data["superseded_at_ms"]),
        fresh_until_ms=None if data.get("fresh_until_ms") is None else int(data["fresh_until_ms"]),
        confidence=float(data.get("confidence") if data.get("confidence") is not None else 0.0),
        authoritative=bool(data.get("authoritative")),
        provenance_hash=str(data.get("provenance_hash") or ""),
        evidence_refs=tuple(str(item) for item in data.get("evidence_refs") or ()),
        meta=dict(data.get("meta") or {}),
        schema_version=int(data.get("schema_version") or 1),
    )


def world_model_semantic_view_from_dict(payload: Mapping[str, Any]) -> WorldModelSemanticViewV1:
    data = dict(payload or {})
    return WorldModelSemanticViewV1(
        state_id=str(data.get("state_id") or ""),
        tenant_id=str(data.get("tenant_id") or ""),
        business_id=str(data.get("business_id") or ""),
        generated_at_ms=int(data.get("generated_at_ms") or 0),
        records=tuple(world_model_semantic_record_from_dict(item) for item in data.get("records") or ()),
        schema_version=str(data.get("schema_version") or WORLD_MODEL_SEMANTICS_SCHEMA_VERSION),
    )


__all__ = [
    "CANON_WORLD_MODEL_SEMANTICS_CONTRACT",
    "WORLD_MODEL_SEMANTIC_KINDS",
    "WORLD_MODEL_SEMANTICS_SCHEMA_VERSION",
    "WorldModelSemanticRecordV1",
    "WorldModelSemanticViewV1",
    "normalize_world_model_semantic_kind",
    "world_model_semantic_record_from_dict",
    "world_model_semantic_view_from_dict",
]
