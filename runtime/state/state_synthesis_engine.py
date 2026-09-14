from __future__ import annotations

from dataclasses import dataclass, field

from runtime.market.market_snapshot import MarketSnapshot
from runtime.market.segment_trend_state import SegmentTrendState
from runtime.state.business_fact_lifecycle import (
    apply_business_fact_supersession,
    validate_business_fact_observation,
)
from runtime.state.state_compaction import StateCompactor
from runtime.state.state_conflict_resolution import (
    apply_conflict_resolution,
    base_observation_from_record,
    carry_unresolved_conflict,
    unresolved_base_conflict,
    validate_conflict_resolutions,
)
from runtime.state.state_conflict_resolver import StateConflictResolver
from runtime.state.state_contract import (
    StateAuditTrailPort,
    StateDeltaLogPort,
    StateObservation,
    StateSnapshotStorePort,
    StateSynthesisRequest,
    StateSynthesizedSnapshot,
)
from runtime.state.state_freshness_policy import NON_DECISION_FRESHNESS_STATUSES, StateFreshnessPolicy
from runtime.state.state_identity import build_state_id
from runtime.state.state_value_projection import materialize_state_values
from runtime.state.world_model_semantic_projector import project_world_model_semantics

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
        for observation in request.observations:
            validate_business_fact_observation(
                observation,
                tenant_id=request.tenant_id,
                business_id=request.business_id,
            )
        base_snapshot = request.base_snapshot
        if base_snapshot is None and self.snapshot_store is not None:
            base_snapshot = self.snapshot_store.load_latest(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
            )

        resolution_by_path = validate_conflict_resolutions(request=request, base_snapshot=base_snapshot)
        grouped = self._group_observations(request.observations)
        if base_snapshot is not None:
            grouped = self._merge_base_snapshot(
                grouped=grouped,
                base_snapshot=base_snapshot,
                now_ms=request.now_ms,
            )

        fields = {}
        conflicts = (
            []
            if base_snapshot is None
            else [item for item in base_snapshot.conflicts if item.status == "resolved"]
        )

        for field_path, observations in sorted(grouped.items()):
            resolved = self._resolver.resolve(
                now_ms=request.now_ms,
                field_path=field_path,
                observations=tuple(observations),
                tenant_id=request.tenant_id,
                business_id=request.business_id,
            )
            record = resolved.record
            base_conflict = unresolved_base_conflict(base_snapshot=base_snapshot, field_path=field_path)
            resolution = resolution_by_path.get(field_path)
            if base_conflict is not None and resolution is not None:
                record, resolved_conflict = apply_conflict_resolution(
                    resolve_field=self._resolver.resolve,
                    freshness_policy=self.freshness_policy,
                    request=request,
                    base_snapshot=base_snapshot,
                    conflict=base_conflict,
                    resolution=resolution,
                )
                conflicts.append(resolved_conflict)
            elif base_conflict is not None:
                record, carried_conflict = carry_unresolved_conflict(
                    resolve_field=self._resolver.resolve,
                    freshness_policy=self.freshness_policy,
                    now_ms=request.now_ms,
                    base_snapshot=base_snapshot,
                    conflict=base_conflict,
                    incoming_observations=tuple(observations),
                )
                conflicts.append(carried_conflict)
            elif resolved.conflict is not None:
                conflicts.append(resolved.conflict)
            fields[field_path] = record

        fields = apply_business_fact_supersession(
            fields=fields,
            now_ms=request.now_ms,
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            freshness_policy=self.freshness_policy,
        )
        values = materialize_state_values(fields)

        snapshot = StateSynthesizedSnapshot(
            state_id=build_state_id(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
                now_ms=request.now_ms,
                fields=fields,
                conflicts=tuple(conflicts),
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
        snapshot = StateSynthesizedSnapshot(
            state_id=snapshot.state_id,
            tenant_id=snapshot.tenant_id,
            business_id=snapshot.business_id,
            synthesized_at_ms=snapshot.synthesized_at_ms,
            schema_version=snapshot.schema_version,
            values=dict(snapshot.values),
            fields=dict(snapshot.fields),
            conflicts=tuple(snapshot.conflicts),
            source_watermarks=dict(snapshot.source_watermarks),
            audit=dict(snapshot.audit),
            meta=dict(snapshot.meta),
            semantic_view=project_world_model_semantics(snapshot),
        )

        if self.snapshot_store is not None:
            self.snapshot_store.save_snapshot(snapshot)
        if self.delta_log is not None:
            self.delta_log.append(previous=base_snapshot, current=snapshot)
        if self.audit_trail is not None:
            self.audit_trail.record(request=request, snapshot=snapshot)

        return snapshot

    def _group_observations(self, observations: tuple[StateObservation, ...]) -> dict[str, list[StateObservation]]:
        grouped: dict[str, list[StateObservation]] = {}
        semantic_kinds_by_path: dict[str, set[str]] = {}
        for item in observations:
            field_path = str(item.field_path)
            semantic_kinds_by_path.setdefault(field_path, set()).add(str(item.semantic_kind))
            grouped.setdefault(field_path, []).append(item)
        mixed = {path: kinds for path, kinds in semantic_kinds_by_path.items() if len(kinds) > 1}
        if mixed:
            details = ", ".join(f"{path}={sorted(kinds)}" for path, kinds in sorted(mixed.items()))
            raise ValueError(f"mixed epistemic kinds for the same field_path are forbidden: {details}")
        return grouped

    def _merge_base_snapshot(
        self,
        *,
        grouped: dict[str, list[StateObservation]],
        base_snapshot: StateSynthesizedSnapshot,
        now_ms: int,
    ) -> dict[str, list[StateObservation]]:
        merged = {key: list(value) for key, value in grouped.items()}
        for field_path, record in base_snapshot.fields.items():
            if field_path in merged:
                incoming_kinds = {str(item.semantic_kind) for item in merged[field_path]}
                if incoming_kinds != {str(record.semantic_kind)}:
                    raise ValueError(
                        "mixed epistemic kinds for the same field_path are forbidden across snapshots: "
                        f"{field_path}={sorted(incoming_kinds | {str(record.semantic_kind)})}"
                    )
            base_observation = base_observation_from_record(
                base_snapshot=base_snapshot,
                field_path=field_path,
                record=record,
            )
            if field_path not in merged:
                merged[field_path] = [base_observation]
                continue
            incoming_not_decision_eligible = all(
                self.freshness_policy.evaluate(now_ms=now_ms, observation=item).status
                in NON_DECISION_FRESHNESS_STATUSES
                for item in merged[field_path]
            )
            base_is_decision_eligible = (
                self.freshness_policy.evaluate(now_ms=now_ms, observation=base_observation).status
                not in NON_DECISION_FRESHNESS_STATUSES
            )
            if incoming_not_decision_eligible and base_is_decision_eligible:
                merged[field_path].append(base_observation)
        return merged

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
    observations.extend(
        _mapping_observations(
            prefix="world.architecture_state",
            source="architecture_state",
            values=architecture_state,
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
    observations.extend(
        _mapping_observations(
            prefix="world.structure_state",
            source="structure_state",
            values=structure_state,
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
    observations.extend(
        _mapping_observations(
            prefix="world.flow_state",
            source="flow_state",
            values=flow_state,
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
    observations.extend(
        _mapping_observations(
            prefix="world.diffusion_state",
            source="diffusion_state",
            values=diffusion_state,
            observed_at_ms=generated_at_ms,
            source_priority=100,
            authoritative=True,
        )
    )
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
    market_state_values = _as_mapping(
        world.get("market_state"),
        {
            "global_macro_score": fallback_market_snapshot.global_macro_score,
            "global_micro_score": fallback_market_snapshot.global_micro_score,
            "global_competitive_shift": fallback_market_snapshot.global_competitive_shift,
        },
    )
    architecture_state = _float_mapping(_as_mapping(world.get("architecture_state"), fallback_architecture_state))
    structure_state = _float_mapping(_as_mapping(world.get("structure_state"), fallback_structure_state))
    flow_state = _float_mapping(_as_mapping(world.get("flow_state"), fallback_flow_state))
    diffusion_state = _float_mapping(_as_mapping(world.get("diffusion_state"), fallback_diffusion_state))

    segment_states = fallback_market_snapshot.segment_states
    raw_segments = (
        world.get("market_state", {}).get("segments") if isinstance(world.get("market_state"), dict) else None
    )
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
        global_macro_score=float(
            market_state_values.get("global_macro_score", fallback_market_snapshot.global_macro_score)
        ),
        global_micro_score=float(
            market_state_values.get("global_micro_score", fallback_market_snapshot.global_micro_score)
        ),
        global_competitive_shift=float(
            market_state_values.get("global_competitive_shift", fallback_market_snapshot.global_competitive_shift)
        ),
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


def _mapping_observations(
    *,
    prefix: str,
    source: str,
    values: dict[str, object],
    observed_at_ms: int,
    source_priority: int,
    authoritative: bool,
) -> list[StateObservation]:
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
