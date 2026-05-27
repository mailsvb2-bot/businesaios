from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.creative import CreativeIntelligenceSnapshot
from runtime.integration.decision_input_bridge import build_decision_input_packet
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.integration.fallback_policy import FallbackPolicy
from runtime.integration.world_state_packet_support import (
    build_advisory_notes,
    build_reward_signal_from_world_view,
    empty_creative_snapshot,
    emit_world_state_materialized_trace,
    emit_world_state_observed_trace,
    emit_world_state_packet_metrics,
    materialize_world_state_packet,
    resolve_world_state_inputs,
)
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability
from runtime.state import StateSynthesisEngine
from runtime.world_state import (
    WorldStateHistoryService,
)


def _record_world_state_trace(*, observability: RuntimeObservability, generated_at_ms: int, synthesized_state) -> None:
    emit_world_state_observed_trace(
        observability=observability,
        generated_at_ms=generated_at_ms,
        synthesized_state=synthesized_state,
    )


@dataclass
class WorldStateIntegrationService:
    observability: RuntimeObservability
    history_service: WorldStateHistoryService | None = None
    state_synthesis_engine: StateSynthesisEngine | None = None
    tenant_id: str = "runtime"
    business_id: str = "default"

    def build_packet(
        self,
        *,
        generated_at_ms: int = 1,
        user_observables: Mapping[str, object] | None = None,
        market_snapshot: MarketSnapshot | None = None,
        creative_snapshots: tuple[CreativeIntelligenceSnapshot, ...] = (),
        architecture_state: Mapping[str, float] | None = None,
        structure_state: Mapping[str, float] | None = None,
        flow_state: Mapping[str, float] | None = None,
        diffusion_state: Mapping[str, float] | None = None,
        advisory_packet: AutonomyAdvisoryPacket | None = None,
        fallback_policy: FallbackPolicy | None = None,
    ) -> DecisionInputPacket:
        resolved = resolve_world_state_inputs(
            generated_at_ms=generated_at_ms,
            user_observables=user_observables,
            market_snapshot=market_snapshot,
            architecture_state=architecture_state,
            structure_state=structure_state,
            flow_state=flow_state,
            diffusion_state=diffusion_state,
            advisory_packet=advisory_packet,
            fallback_policy=fallback_policy,
            tenant_id=self.tenant_id,
            business_id=self.business_id,
            state_synthesis_engine=self.state_synthesis_engine,
        )
        synthesized_state = resolved["synthesized_state"]
        reward_signal = build_reward_signal_from_world_view(
            creative_snapshots=creative_snapshots,
            architecture_state=resolved["architecture_state"],
            structure_state=resolved["structure_state"],
            flow_state=resolved["flow_state"],
            market_snapshot=resolved["market_snapshot"],
            fallback_snapshot=empty_creative_snapshot(),
        )
        advisory_notes = build_advisory_notes(
            synthesized_state=synthesized_state,
            advisory_packet=resolved["advisory_packet"],
            notes=resolved["notes"],
            reward_signal=reward_signal,
        )

        _record_world_state_trace(
            observability=self.observability,
            generated_at_ms=generated_at_ms,
            synthesized_state=synthesized_state,
        )

        materialized = materialize_world_state_packet(
            generated_at_ms=generated_at_ms,
            resolved=resolved,
            creative_snapshots=creative_snapshots,
            reward_signal=reward_signal,
            advisory_notes=advisory_notes,
            history_service=self.history_service,
        )
        advisory_packet = materialized["advisory_packet"]
        history_summary = materialized["history_summary"]
        packet = materialized["packet"]
        emit_world_state_packet_metrics(
            observability=self.observability,
            advisory_packet=advisory_packet,
            history_summary=history_summary,
        )
        emit_world_state_materialized_trace(
            observability=self.observability,
            generated_at_ms=generated_at_ms,
            advisory_packet=advisory_packet,
            history_summary=history_summary,
        )
        return build_decision_input_packet(packet)
