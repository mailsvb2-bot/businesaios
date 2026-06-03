from __future__ import annotations

"""Support helpers for the canonical world-state packet path.

These helpers keep the runtime integration service thin while preserving the
existing single canonical packet-building route. They do not issue decisions
and do not contain alternate runtime wiring.
"""

from collections.abc import Mapping

from core.world_state.packet_enrichment import (
    build_advisory_notes,
    build_reward_signal_from_world_view,
)
from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.creative import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from runtime.integration.fallback_policy import (
    TEST_FALLBACK_POLICY,
    FallbackPolicy,
    apply_world_view_with_policy,
)
from runtime.integration.input_resolution import (
    resolve_advisory_packet,
    resolve_architecture_state,
    resolve_diffusion_state,
    resolve_flow_state,
    resolve_market_snapshot,
    resolve_structure_state,
    resolve_user_observables,
)
from runtime.market.market_snapshot import MarketSnapshot
from runtime.state import (
    StateSynthesisEngine,
    StateSynthesisRequest,
    build_world_state_observations,
)
from runtime.world_state import (
    HistorySummary,
    WorldStateHistoryService,
    assemble_world_state,
    build_recommendation_packet,
)


def resolve_world_state_inputs(
    *,
    generated_at_ms: int,
    user_observables: Mapping[str, object] | None,
    market_snapshot: MarketSnapshot | None,
    architecture_state: Mapping[str, float] | None,
    structure_state: Mapping[str, float] | None,
    flow_state: Mapping[str, float] | None,
    diffusion_state: Mapping[str, float] | None,
    advisory_packet: AutonomyAdvisoryPacket | None,
    fallback_policy: FallbackPolicy | None,
    tenant_id: str,
    business_id: str,
    state_synthesis_engine: StateSynthesisEngine | None,
) -> dict[str, object]:
    policy = TEST_FALLBACK_POLICY if fallback_policy is None else fallback_policy
    notes: tuple[str, ...] = ()
    user_observables, notes = resolve_user_observables(user_observables, policy, notes)
    market_snapshot, notes = resolve_market_snapshot(market_snapshot, policy, notes)
    architecture_state, notes = resolve_architecture_state(architecture_state, policy, notes)
    structure_state, notes = resolve_structure_state(structure_state, policy, notes)
    flow_state, notes = resolve_flow_state(flow_state, policy, notes)
    diffusion_state, notes = resolve_diffusion_state(diffusion_state, policy, notes)
    advisory_packet, notes = resolve_advisory_packet(advisory_packet, policy, notes)

    architecture_state = dict(architecture_state)
    structure_state = dict(structure_state)
    flow_state = dict(flow_state)
    diffusion_state = dict(diffusion_state)
    user_observables = dict(user_observables)

    engine = state_synthesis_engine or StateSynthesisEngine()
    synthesized_state = engine.synthesize(
        StateSynthesisRequest(
            tenant_id=tenant_id,
            business_id=business_id,
            now_ms=generated_at_ms,
            observations=build_world_state_observations(
                generated_at_ms=generated_at_ms,
                user_observables=user_observables,
                market_snapshot=market_snapshot,
                architecture_state=architecture_state,
                structure_state=structure_state,
                flow_state=flow_state,
                diffusion_state=diffusion_state,
            ),
            correlation_id=f"world-state:{generated_at_ms}",
            meta={"surface": "runtime.integration.world_state_integration_service"},
        )
    )
    user_observables, market_snapshot, architecture_state, structure_state, flow_state, diffusion_state = apply_world_view_with_policy(
        snapshot=synthesized_state,
        user_observables=user_observables,
        market_snapshot=market_snapshot,
        architecture_state=architecture_state,
        structure_state=structure_state,
        flow_state=flow_state,
        diffusion_state=diffusion_state,
    )
    return {
        "notes": notes,
        "user_observables": user_observables,
        "market_snapshot": market_snapshot,
        "architecture_state": architecture_state,
        "structure_state": structure_state,
        "flow_state": flow_state,
        "diffusion_state": diffusion_state,
        "advisory_packet": advisory_packet,
        "synthesized_state": synthesized_state,
    }




def empty_creative_snapshot() -> CreativeIntelligenceSnapshot:
    return CreativeIntelligenceSnapshot(
        creative_id="none",
        pnl=CreativePnLSnapshot(
            creative_id="none",
            attributed_revenue=0.0,
            total_cost=0.0,
            contribution_profit=0.0,
            contribution_margin_ratio=0.0,
            roi=0.0,
        ),
        incrementality=IncrementalitySnapshot(
            creative_id="none",
            estimated_effect=0.0,
            confidence_score=0.0,
            downside_risk=1.0,
            method="none",
        ),
        experiment_confidence=ExperimentConfidenceSnapshot(
            creative_id="none",
            uplift=0.0,
            p_value=1.0,
            confidence_score=0.0,
            rollout_readiness=0.0,
        ),
        expected_value_score=0.0,
        downside_envelope=1.0,
        portfolio_rank_score=0.0,
        explanations=(),
    )


def emit_world_state_observed_trace(*, observability, generated_at_ms: int, synthesized_state) -> None:
    observability.record_world_state_trace(
        trace_name="state_synthesis",
        stage="observed",
        generated_at_ms=generated_at_ms,
        field_count=len(synthesized_state.fields),
        conflict_count=len(synthesized_state.conflicts),
    )


def emit_world_state_materialized_trace(*, observability, generated_at_ms: int, advisory_packet: AutonomyAdvisoryPacket, history_summary: HistorySummary | None) -> None:
    observability.record_world_state_trace(
        trace_name="decision_input_packet",
        stage="materialized",
        generated_at_ms=generated_at_ms,
        recommendation_count=len(advisory_packet.recommendations),
        history_sample_count=0 if history_summary is None else int(history_summary.sample_count),
    )


def emit_world_state_packet_metrics(*, observability, advisory_packet: AutonomyAdvisoryPacket, history_summary: HistorySummary | None) -> None:
    observability.record_advisory_packet_built(
        packet_name="decision_input_packet",
        recommendation_count=len(advisory_packet.recommendations),
    )
    if history_summary is not None:
        observability.record_model_snapshot(
            model_name="world_state_history",
            metric_name="sample_count",
            metric_value=float(history_summary.sample_count),
        )


def materialize_world_state_packet(
    *,
    generated_at_ms: int,
    resolved: Mapping[str, object],
    creative_snapshots: tuple[CreativeIntelligenceSnapshot, ...],
    reward_signal: float,
    advisory_notes: tuple[str, ...],
    history_service: WorldStateHistoryService | None,
) -> dict[str, object]:
    advisory_packet = AutonomyAdvisoryPacket(
        packet_name=resolved["advisory_packet"].packet_name,
        recommendations=resolved["advisory_packet"].recommendations,
        notes=advisory_notes,
    )
    world_state = assemble_world_state(
        generated_at_ms=generated_at_ms,
        user_observables=resolved["user_observables"],
        market_snapshot=resolved["market_snapshot"],
        creative_snapshots=creative_snapshots,
        architecture_state=resolved["architecture_state"],
        structure_state=resolved["structure_state"],
        flow_state=resolved["flow_state"],
        diffusion_state=resolved["diffusion_state"],
        reward_signal=reward_signal,
        history_summary=None,
        advisory_flags={"packet_name": advisory_packet.packet_name},
        notes=advisory_notes,
    )
    history_summary: HistorySummary | None = None
    if history_service is not None:
        history_summary = history_service.record(world_state)
        world_state = assemble_world_state(
            generated_at_ms=generated_at_ms,
            user_observables=resolved["user_observables"],
            market_snapshot=resolved["market_snapshot"],
            creative_snapshots=creative_snapshots,
            architecture_state=resolved["architecture_state"],
            structure_state=resolved["structure_state"],
            flow_state=resolved["flow_state"],
            diffusion_state=resolved["diffusion_state"],
            reward_signal=reward_signal,
            history_summary=history_summary,
            advisory_flags={"packet_name": advisory_packet.packet_name},
            notes=advisory_notes,
        )
    packet = build_recommendation_packet(
        packet_id=world_state.state_id,
        world_state=world_state,
        recommendations=tuple(advisory_packet.recommendations),
        explanation_lines=tuple(advisory_notes),
    )
    return {
        "advisory_packet": advisory_packet,
        "world_state": world_state,
        "history_summary": history_summary,
        "packet": packet,
    }


__all__ = [
    "build_advisory_notes",
    "build_reward_signal_from_world_view",
    "materialize_world_state_packet",
    "empty_creative_snapshot",
    "emit_world_state_materialized_trace",
    "emit_world_state_packet_metrics",
    "emit_world_state_observed_trace",
    "resolve_world_state_inputs",
]
