from __future__ import annotations

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.audit_log import RuntimeAuditLog
from runtime.decision_input.decision_input_service import DecisionInputService
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.runtime_observability import RuntimeObservability


def test_decision_input_service_reads_packet() -> None:
    service = DecisionInputService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    contract = service.read_packet(
        DecisionInputPacket(
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
    )
    assert contract.envelope.packet_id == "p1"
