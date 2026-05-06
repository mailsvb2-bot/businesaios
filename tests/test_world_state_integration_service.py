from __future__ import annotations

from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.audit_log import RuntimeAuditLog
from runtime.integration.world_state_integration_service import WorldStateIntegrationService
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability


def test_world_state_integration_service_builds_packet() -> None:
    service = WorldStateIntegrationService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    packet = service.build_packet(
        generated_at_ms=111,
        user_observables={
            "intent_index": 0.6,
            "trust_index": 0.7,
            "value_index": 0.5,
            "payment_readiness_index": 0.4,
            "fatigue_index": 0.2,
            "hesitation_score": 0.1,
            "buy_vector": 0.5,
            "churn_vector": 0.2,
            "coherence_score": 0.8,
        },
        market_snapshot=MarketSnapshot(
            global_macro_score=0.6,
            global_micro_score=0.5,
            global_competitive_shift=0.3,
            segment_states=(),
        ),
        creative_snapshots=(),
        architecture_state={"global_stability": 0.8},
        structure_state={"curvature": 0.2, "boundary_pressure": 0.3, "blast_radius_risk": 0.25},
        flow_state={"velocity": 0.5, "pressure": 0.4, "turbulence": 0.1},
        diffusion_state={"spread_index": 0.45, "saturation_risk": 0.2, "viral_potential": 0.4},
        advisory_packet=AutonomyAdvisoryPacket(
            packet_name="autonomy_advisory_v1",
            recommendations=[],
            notes=("note",),
        ),
    )
    assert packet.recommendation_packet.packet_id


def test_world_state_integration_service_emits_state_synthesis_note() -> None:
    service = WorldStateIntegrationService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    packet = service.build_packet(
        generated_at_ms=222,
        user_observables={
            "intent_index": 0.6,
            "trust_index": 0.7,
            "value_index": 0.5,
            "payment_readiness_index": 0.4,
            "fatigue_index": 0.2,
            "hesitation_score": 0.1,
            "buy_vector": 0.5,
            "churn_vector": 0.2,
            "coherence_score": 0.8,
        },
        market_snapshot=MarketSnapshot(
            global_macro_score=0.6,
            global_micro_score=0.5,
            global_competitive_shift=0.3,
            segment_states=(),
        ),
        creative_snapshots=(),
        architecture_state={"global_stability": 0.8},
        structure_state={"curvature": 0.2, "boundary_pressure": 0.3, "blast_radius_risk": 0.25},
        flow_state={"velocity": 0.5, "pressure": 0.4, "turbulence": 0.1},
        diffusion_state={"spread_index": 0.45, "saturation_risk": 0.2, "viral_potential": 0.4},
        advisory_packet=AutonomyAdvisoryPacket(
            packet_name="autonomy_advisory_v1",
            recommendations=[],
            notes=("note",),
        ),
    )
    assert any(str(item).startswith("state_synthesis:") for item in packet.recommendation_packet.explanation_lines)


def test_world_state_integration_service_emits_trace_story_events() -> None:
    service = WorldStateIntegrationService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    service.build_packet(generated_at_ms=11, user_observables={"sessions": 1})
    events = service.observability.audit_log.records()
    trace_events = [event for event in events if event.name == "runtime_trace_story"]
    assert trace_events
    assert {event.payload.get("trace_kind") for event in trace_events} == {"world_state"}
