from __future__ import annotations

from dataclasses import dataclass

from runtime.creative import CreativeIntelligenceSnapshot
from runtime.explainability import assert_non_decision_payload, build_creative_reasons, to_lines
from runtime.advisory.action_phase import HOLD, LAUNCH, REALLOCATE, SCALE, SELECT, STOP
from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability
from config.decision_safety_policy import DEFAULT_AUTONOMY_ADVISORY_POLICY


def _phase_for(snapshot: CreativeIntelligenceSnapshot) -> str:
    policy = DEFAULT_AUTONOMY_ADVISORY_POLICY
    if snapshot.expected_value_score > policy.scale_expected_value_threshold and snapshot.downside_envelope < policy.scale_downside_ceiling:
        return SCALE
    if snapshot.expected_value_score > policy.launch_expected_value_threshold and snapshot.experiment_confidence.rollout_readiness > policy.launch_rollout_readiness_threshold:
        return LAUNCH
    if snapshot.expected_value_score < policy.stop_expected_value_threshold or snapshot.downside_envelope > policy.stop_downside_threshold:
        return STOP
    if snapshot.incrementality.confidence_score < policy.select_confidence_threshold:
        return SELECT
    if snapshot.expected_value_score >= 0.0:
        return REALLOCATE
    return HOLD


@dataclass
class AutonomyAdvisorService:
    observability: RuntimeObservability

    def build_packet(
        self,
        *,
        market_snapshot: MarketSnapshot,
        ranked_creatives: tuple[CreativeIntelligenceSnapshot, ...],
        architecture_global_stability: float,
        flow_turbulence: float,
    ) -> AutonomyAdvisoryPacket:
        recommendations: list[dict[str, object]] = []
        notes: list[str] = []

        for snapshot in ranked_creatives:
            phase = _phase_for(snapshot)
            for line in to_lines(build_creative_reasons(snapshot)):
                if line not in notes:
                    notes.append(line)
            recommendations.append(
                {
                    "kind": "autonomy_advisory",
                    "creative_id": snapshot.creative_id,
                    "phase": phase,
                    "portfolio_rank_score": snapshot.portfolio_rank_score,
                    "expected_value_score": snapshot.expected_value_score,
                    "downside_envelope": snapshot.downside_envelope,
                    "market_macro_score": market_snapshot.global_macro_score,
                    "market_micro_score": market_snapshot.global_micro_score,
                    "architecture_global_stability": architecture_global_stability,
                    "flow_turbulence": flow_turbulence,
                    "explanation": (
                        f"phase={phase}; ev={snapshot.expected_value_score:.3f}; "
                        f"downside={snapshot.downside_envelope:.3f}; "
                        f"market_micro={market_snapshot.global_micro_score:.3f}"
                    ),
                }
            )

        policy = DEFAULT_AUTONOMY_ADVISORY_POLICY
        if architecture_global_stability < policy.architecture_stability_low_threshold:
            notes.append("architecture stability is low; DecisionCore should prefer conservative actions")
        if flow_turbulence > policy.flow_turbulence_high_threshold:
            notes.append("flow turbulence is elevated; DecisionCore should avoid aggressive scaling")
        if market_snapshot.global_competitive_shift > policy.competitive_shift_high_threshold:
            notes.append("competitive shift is high; DecisionCore should increase evidence requirements")

        safe_recommendations = assert_non_decision_payload(recommendations)
        self.observability.record_advisory_packet_built(
            packet_name="autonomy_advisory_v1",
            recommendation_count=len(safe_recommendations),
        )
        return AutonomyAdvisoryPacket(
            packet_name="autonomy_advisory_v1",
            recommendations=safe_recommendations,
            notes=tuple(notes),
        )

    def build_advisory_packet(self) -> dict[str, object]:
        packet = self.build_packet(
            market_snapshot=MarketSnapshot(
                global_macro_score=0.58,
                global_micro_score=0.54,
                global_competitive_shift=0.22,
                segment_states=(),
            ),
            ranked_creatives=(),
            architecture_global_stability=0.82,
            flow_turbulence=0.14,
        )
        return {
            "packet_name": packet.packet_name,
            "recommendations": tuple(dict(item) for item in packet.recommendations),
            "notes": packet.notes,
        }
