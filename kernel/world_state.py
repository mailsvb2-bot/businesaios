from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from contracts.world_model_semantics import (
    WorldModelSemanticRecordV1,
    WorldModelSemanticViewV1,
)
from core.utils.canonical import canonical_json_bytes


@dataclass(frozen=True)
class WorldStateV1:
    """Canonical WorldState.

    Requirements:
    - versioned schema (schema_version)
    - canonicalizable/deterministic serialization
    - includes all fields relevant for decisions (including deployment proposals)
    """

    schema_version: int
    user: dict[str, Any]
    session: dict[str, Any]
    product: dict[str, Any]
    economy: dict[str, Any]
    timestamp_ms: int

    # Tenant isolation (must be propagated everywhere)
    tenant_id: str = "default"
    meta: dict[str, Any] = field(default_factory=dict)

    # Additional canonical fields:
    user_id: str | None = None
    safe_mode: bool = False

    # Economic governance fields (required in strict prod)
    capital: float = 0.0
    horizon_state: str = "stable"

    # Behavioral snapshot (read-model input for DecisionCore; optional)
    behavior: dict[str, Any] | None = None

    # DecisionCore-issued constraints for pricing/offer selection (no second brain)
    # Example: {"max_band": "low"|"standard"|"premium"}
    price_constraints: dict[str, Any] | None = None

    # Self-driving deployment proposal (set by LearningSystem; DecisionCore decides)
    deployment_proposal: dict[str, Any] | None = None

    # Safe human override request (still decided by DecisionCore)
    manual_override: bool = False

    # Canonical semantic view over the same sovereign state; never a second WorldState.
    world_model_semantics: WorldModelSemanticViewV1 | None = None

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(asdict(self))


def _semantic_record_from_canonical_mapping(
    payload: Mapping[str, Any],
) -> WorldModelSemanticRecordV1:
    data = dict(payload)
    try:
        evidence_refs = data["evidence_refs"]
        meta = data["meta"]
        if not isinstance(evidence_refs, list | tuple):
            raise TypeError("evidence_refs must be a sequence")
        if not isinstance(meta, Mapping):
            raise TypeError("meta must be a mapping")
        return WorldModelSemanticRecordV1(
            record_id=data["record_id"],
            tenant_id=data["tenant_id"],
            business_id=data["business_id"],
            epistemic_type=data["epistemic_type"],
            key=data["key"],
            value=data["value"],
            source=data["source"],
            occurred_at_ms=data["occurred_at_ms"],
            observed_at_ms=data["observed_at_ms"],
            recorded_at_ms=data["recorded_at_ms"],
            confidence=data["confidence"],
            authoritative=data["authoritative"],
            provenance_hash=data["provenance_hash"],
            valid_from_ms=data["valid_from_ms"],
            valid_until_ms=data["valid_until_ms"],
            superseded_at_ms=data["superseded_at_ms"],
            fresh_until_ms=data["fresh_until_ms"],
            evidence_refs=tuple(evidence_refs),
            meta=dict(meta),
            schema_version=data["schema_version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid canonical world-model semantic record") from exc


def _semantic_view_from_canonical_mapping(
    payload: Mapping[str, Any],
) -> WorldModelSemanticViewV1:
    data = dict(payload)
    try:
        raw_records = data["records"]
        if not isinstance(raw_records, list | tuple):
            raise TypeError("records must be a sequence")
        records = []
        for item in raw_records:
            if not isinstance(item, Mapping):
                raise TypeError("semantic record must be a mapping")
            records.append(_semantic_record_from_canonical_mapping(item))
        return WorldModelSemanticViewV1(
            state_id=data["state_id"],
            tenant_id=data["tenant_id"],
            business_id=data["business_id"],
            generated_at_ms=data["generated_at_ms"],
            records=tuple(records),
            schema_version=data["schema_version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid canonical world-model semantic view") from exc


def world_state_from_canonical_bytes(raw: bytes) -> WorldStateV1:
    """Decode canonical WorldState bytes without compatibility coercions.

    Historical replay and asynchronous shadow evaluation must preserve every
    serialized value exactly enough for a byte-for-byte canonical round trip.
    Compatibility/defaulting helpers are intentionally not used here.
    """

    try:
        payload = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid canonical world-state bytes") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("canonical world state must be a mapping")

    data = dict(payload)
    semantics = data.get("world_model_semantics")
    if semantics is not None:
        if not isinstance(semantics, Mapping):
            raise ValueError("canonical world-model semantics must be a mapping")
        data["world_model_semantics"] = _semantic_view_from_canonical_mapping(semantics)

    try:
        return WorldStateV1(**data)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid canonical world-state payload") from exc


"""NOTE:

This module intentionally exposes a *single* canonical WorldState.

Do NOT add additional public WorldState variants ("V2", "TelegramWorldState", etc.).
Multiple competing state schemas create a hidden "second brain" via alternative paths.
"""
