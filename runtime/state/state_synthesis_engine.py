from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from runtime.market.market_snapshot import MarketSnapshot
from runtime.market.segment_trend_state import SegmentTrendState
from runtime.state.state_compaction import StateCompactor
from runtime.state.state_conflict_resolver import StateConflictResolver
from runtime.state.state_contract import (
    StateAuditTrailPort,
    StateDeltaLogPort,
    StateObservation,
    StateSnapshotStorePort,
    StateSynthesisRequest,
    StateSynthesizedSnapshot,
)
from runtime.state.state_freshness_policy import StateFreshnessPolicy


CANON_STATE_SYNTHESIS_ENGINE = True
STATE_SYNTHESIS_DOES_NOT_OWN_DECISIONS = True


@dataclass
class StateSynthesisEngine:
    snapshot_store: StateSnapshotStorePort | None = None
    delta_log: StateDeltaLogPort | None = None
    audit_trail: StateAuditTrailPort | None = None
    freshness_policy: StateFreshnessPolicy = field(default_factory=StateFreshnessPolicy)
    compactor: StateCompactor = field(default_factory=StateCompactor)

    def __post_init__(self) -> None:
        self._resolver = StateConflictResolver(freshness_policy=self.freshness_policy)

    def synthesize(self, request: StateSynthesisRequest) -> StateSynthesizedSnapshot:
        base_snapshot = request.base_snapshot
        if base_snapshot is None and self.snapshot_store is not None:
            base_snapshot = self.snapshot_store.load_latest(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
            )

        grouped = self._group_observations(request.observations)
        if base_snapshot is not None:
            grouped = self._merge_base_snapshot(grouped=grouped, base_snapshot=base_snapshot)

        fields = {}
        conflicts = []

        for field_path, observations in sorted(grouped.items()):
            resolved = self._resolver.resolve(
                now_ms=request.now_ms,
                field_path=field_path,
                observations=tuple(observations),
            )
            fields[field_path] = resolved.record
            if resolved.conflict is not None:
                conflicts.append(resolved.conflict)

        values = self._materialize_values(fields)

        snapshot = StateSynthesizedSnapshot(
            state_id=self._build_state_id(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
                now_ms=request.now_ms,
                fields=fields,
            ),
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            synthesized_at_ms=int(request.now_ms),
            values=values,
            fields=fields,
            conflicts=tuple(conflicts),
            source_watermarks=self._source_watermarks(request.observations, base_snapshot=base_snapshot),
            audit={
                "observation_count": len(request.observations),
                "field_count": len(fields),
                "conflict_count": len(conflicts),
                "base_state_id": None if base_snapshot is None else base_snapshot.state_id,
                "correlation_id": request.correlation_id,
            },
            meta=dict(request.meta),
        )

        snapshot = self.compactor.compact(snapshot)

        if self.snapshot_store is not None:
            self.snapshot_store.save_snapshot(snapshot)
        if self.delta_log is not None:
            self.delta_log.append(previous=base_snapshot, current=snapshot)
        if self.audit_trail is not None:
            self.audit_trail.record(request=request, snapshot=snapshot)

        return snapshot

    def _group_observations(self, observations: tuple[StateObservation, ...]) -> dict[str, list[StateObservation]]:
        grouped: dict[str, list[StateObservation]] = {}
        for item in observations:
            grouped.setdefault(str(item.field_path), []).append(item)
        return grouped

    def _merge_base_snapshot(
        self,
        *,
        grouped: dict[str, list[StateObservation]],
        base_snapshot: StateSynthesizedSnapshot,
    ) -> dict[str, list[StateObservation]]:
        merged = {key: list(value) for key, value in grouped.items()}
        for field_path, record in base_snapshot.fields.items():
            if field_path in merged:
                continue
            merged[field_path] = [
                StateObservation(
                    field_path=field_path,
                    value=record.value,
                    source=f"snapshot:{record.source}",
                    observed_at_ms=int(record.observed_at_ms),
                    recorded_at_ms=int(record.recorded_at_ms),
                    confidence=float(record.confidence),
                    source_priority=int(record.source_priority),
                    authoritative=bool(record.authoritative),
                    ttl_ms=record.meta.get("effective_ttl_ms"),
                    unknown=record.value_kind == "unknown",
                    absent=record.value_kind == "absent",
                    evidence_refs=tuple(record.evidence_refs),
                    meta={"hydrated_from_state_id": base_snapshot.state_id},
                )
            ]
        return merged

    def _materialize_values(self, fields: dict[str, Any]) -> dict[str, Any]:
        root: dict[str, Any] = {}
        for field_path, record in fields.items():
            target = root
            parts = [part for part in str(field_path).split(".") if part]
            if not parts:
                continue
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = record.value
        return root

    def _source_watermarks(
        self,
        observations: tuple[StateObservation, ...],
        *,
        base_snapshot: StateSynthesizedSnapshot | None,
    ) -> dict[str, int]:
        watermarks = {} if base_snapshot is None else dict(base_snapshot.source_watermarks)
        for item in observations:
            watermarks[str(item.source)] = max(int(item.observed_at_ms), int(watermarks.get(str(item.source), 0) or 0))
        return watermarks

    def _build_state_id(self, *, tenant_id: str, business_id: str, now_ms: int, fields: dict[str, Any]) -> str:
        payload = {
            "tenant_id": str(tenant_id),
            "business_id": str(business_id),
            "now_ms": int(now_ms),
            "fields": {key: value.provenance_hash for key, value in sorted(fields.items())},
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:24]


def build_world_state_observations(
    *,
    generated_at_ms: int,
    user_observables: dict[str, object],
    market_snapshot: MarketSnapshot,
    architecture_state: dict[str, float],
    structure_state: dict[str, float],
    flow_state: dict[str, float],
    diffusion_state: dict[str, float],
) -> tuple[StateObservation, ...]:
    observations: list[StateObservation] = []
    observations.extend(
        _mapping_observations(
            prefix="world.user_state",
            source="user_observables",
            values=user_observables,
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
    observations.extend(
        _mapping_observations(
            prefix="world.market_state",
            source="market_snapshot",
            values={
                "global_macro_score": market_snapshot.global_macro_score,
                "global_micro_score": market_snapshot.global_micro_score,
                "global_competitive_shift": market_snapshot.global_competitive_shift,
            },
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
    for segment in market_snapshot.segment_states:
        observations.extend(
            _mapping_observations(
                prefix=f"world.market_state.segments.{segment.segment_key}",
                source="market_snapshot.segment",
                values={
                    "macro_score": segment.macro_score,
                    "micro_score": segment.micro_score,
                    "persistence_score": segment.persistence_score,
                    "competitive_shift_score": segment.competitive_shift_score,
                },
                observed_at_ms=generated_at_ms,
                source_priority=95,
                authoritative=True,
            )
        )
    observations.extend(_mapping_observations(prefix="world.architecture_state", source="architecture_state", values=architecture_state, observed_at_ms=generated_at_ms, source_priority=100, authoritative=True))
    observations.extend(_mapping_observations(prefix="world.structure_state", source="structure_state", values=structure_state, observed_at_ms=generated_at_ms, source_priority=100, authoritative=True))
    observations.extend(_mapping_observations(prefix="world.flow_state", source="flow_state", values=flow_state, observed_at_ms=generated_at_ms, source_priority=100, authoritative=True))
    observations.extend(_mapping_observations(prefix="world.diffusion_state", source="diffusion_state", values=diffusion_state, observed_at_ms=generated_at_ms, source_priority=100, authoritative=True))
    return tuple(observations)


def apply_synthesized_world_view(
    *,
    snapshot: StateSynthesizedSnapshot,
    fallback_user_observables: dict[str, object],
    fallback_market_snapshot: MarketSnapshot,
    fallback_architecture_state: dict[str, float],
    fallback_structure_state: dict[str, float],
    fallback_flow_state: dict[str, float],
    fallback_diffusion_state: dict[str, float],
) -> tuple[dict[str, object], MarketSnapshot, dict[str, float], dict[str, float], dict[str, float], dict[str, float]]:
    world = dict(snapshot.values.get("world") or {})

    user_state = _as_mapping(world.get("user_state"), fallback_user_observables)
    market_state_values = _as_mapping(world.get("market_state"), {
        "global_macro_score": fallback_market_snapshot.global_macro_score,
        "global_micro_score": fallback_market_snapshot.global_micro_score,
        "global_competitive_shift": fallback_market_snapshot.global_competitive_shift,
    })
    architecture_state = _float_mapping(_as_mapping(world.get("architecture_state"), fallback_architecture_state))
    structure_state = _float_mapping(_as_mapping(world.get("structure_state"), fallback_structure_state))
    flow_state = _float_mapping(_as_mapping(world.get("flow_state"), fallback_flow_state))
    diffusion_state = _float_mapping(_as_mapping(world.get("diffusion_state"), fallback_diffusion_state))

    segment_states = fallback_market_snapshot.segment_states
    raw_segments = world.get("market_state", {}).get("segments") if isinstance(world.get("market_state"), dict) else None
    if isinstance(raw_segments, dict) and raw_segments:
        rebuilt_segments: list[SegmentTrendState] = []
        for segment_key, raw_values in sorted(raw_segments.items()):
            values = _float_mapping(_as_mapping(raw_values, {}))
            rebuilt_segments.append(
                SegmentTrendState(
                    segment_key=str(segment_key),
                    macro_score=float(values.get("macro_score", 0.0)),
                    micro_score=float(values.get("micro_score", 0.0)),
                    persistence_score=float(values.get("persistence_score", 0.0)),
                    competitive_shift_score=float(values.get("competitive_shift_score", 0.0)),
                )
            )
        segment_states = tuple(rebuilt_segments)

    market_snapshot = MarketSnapshot(
        global_macro_score=float(market_state_values.get("global_macro_score", fallback_market_snapshot.global_macro_score)),
        global_micro_score=float(market_state_values.get("global_micro_score", fallback_market_snapshot.global_micro_score)),
        global_competitive_shift=float(market_state_values.get("global_competitive_shift", fallback_market_snapshot.global_competitive_shift)),
        segment_states=segment_states,
    )

    return (
        dict(user_state),
        market_snapshot,
        architecture_state,
        structure_state,
        flow_state,
        diffusion_state,
    )


def _mapping_observations(*, prefix: str, source: str, values: dict[str, object], observed_at_ms: int, source_priority: int, authoritative: bool) -> list[StateObservation]:
    observations: list[StateObservation] = []
    for key, value in sorted(values.items()):
        observations.append(
            StateObservation(
                field_path=f"{prefix}.{key}",
                value=value,
                source=source,
                observed_at_ms=observed_at_ms,
                source_priority=source_priority,
                authoritative=authoritative,
            )
        )
    return observations


def _as_mapping(value: object, fallback: dict[str, object]) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return dict(fallback)


def _float_mapping(value: dict[str, object]) -> dict[str, float]:
    return {str(key): float(item) for key, item in value.items()}
