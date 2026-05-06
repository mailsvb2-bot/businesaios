from __future__ import annotations

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.audit_log import RuntimeAuditLog
from runtime.decision_gateway import DecisionGateway
from runtime.decision_input.decision_input_service import DecisionInputService
from runtime.decision_input.runtime_state_enrichment import RuntimeStateEnrichmentService
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.runtime_observability import RuntimeObservability


def test_decision_gateway_only_enriches_and_calls_core() -> None:
    obs = RuntimeObservability(audit_log=RuntimeAuditLog())
    gateway = DecisionGateway(
        decision_input_service=DecisionInputService(observability=obs),
        enrichment_service=RuntimeStateEnrichmentService(observability=obs),
        observability=obs,
    )

    packet = DecisionInputPacket(
        recommendation_packet=RecommendationPacketContract(
            packet_id="p1",
            world_state=WorldStateContract(
                state_id="s1",
                generated_at_ms=1,
                user_state={"intent": 0.5},
                market_state={},
                creative_state={},
                architecture_state={},
                structure_state={},
                flow_state={},
                diffusion_state={},
                economics_state={},
                reward_state={},
                advisory_flags={},
                notes=(),
            ),
            recommendations=(),
            explanation_lines=(),
        )
    )

    def fake_core(ctx: dict[str, object]) -> dict[str, object]:
        assert "external_world_state_features" in ctx
        assert "winner" not in ctx
        return {"ok": True}

    result = gateway.route(
        packet=packet,
        canonical_context={"base": 1},
        decision_core_callable=fake_core,
    )
    assert result == {"ok": True}
