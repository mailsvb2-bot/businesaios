from __future__ import annotations

from runtime.advisory.autonomy_advisory_packet import AutonomyAdvisoryPacket
from runtime.audit_log import RuntimeAuditLog
from runtime.decision_gateway import DecisionGateway
from runtime.decision_input.decision_input_service import DecisionInputService
from runtime.decision_input.runtime_state_enrichment import RuntimeStateEnrichmentService
from runtime.integration.runtime_packet_provider import RuntimePacketProvider
from runtime.integration.runtime_packet_request import RuntimePacketRequest
from runtime.integration.world_state_integration_service import WorldStateIntegrationService
from runtime.market.market_snapshot import MarketSnapshot
from runtime.runtime_observability import RuntimeObservability


def test_single_canonical_packet_path() -> None:
    obs = RuntimeObservability(audit_log=RuntimeAuditLog())
    provider = RuntimePacketProvider(
        integration_service=WorldStateIntegrationService(observability=obs),
        observability=obs,
    )
    gateway = DecisionGateway(
        decision_input_service=DecisionInputService(observability=obs),
        enrichment_service=RuntimeStateEnrichmentService(observability=obs),
        observability=obs,
    )

    packet = provider.build(
        RuntimePacketRequest(
            generated_at_ms=1,
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
                global_competitive_shift=0.2,
                segment_states=(),
            ),
            creative_snapshots=(),
            architecture_state={"global_stability": 0.8},
            structure_state={"curvature": 0.2, "boundary_pressure": 0.3, "blast_radius_risk": 0.2},
            flow_state={"velocity": 0.5, "pressure": 0.4, "turbulence": 0.1},
            diffusion_state={"spread_index": 0.4, "saturation_risk": 0.2, "viral_potential": 0.35},
            advisory_packet=AutonomyAdvisoryPacket(
                packet_name="autonomy_advisory_v1",
                recommendations=(),
                notes=(),
            ),
        )
    )

    def fake_core(ctx: dict[str, object]) -> dict[str, object]:
        assert "external_world_state_features" in ctx
        assert "external_packet_id" in ctx
        assert "winner" not in ctx
        assert "candidate_ids" not in ctx
        return {"ok": True}

    result = gateway.route(
        packet=packet,
        canonical_context={"base": 1},
        decision_core_callable=fake_core,
    )
    assert result == {"ok": True}
