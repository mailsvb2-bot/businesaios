from __future__ import annotations

from application.decisioning.decision_core_input_bridge import build_decision_core_enrichment
from contracts.decisioning.decision_envelope_contract import DecisionEnvelopeContract
from contracts.decisioning.decision_input_contract import DecisionInputContract


def test_decision_core_input_bridge_builds_safe_payload() -> None:
    enrichment = build_decision_core_enrichment(
        DecisionInputContract(
            envelope=DecisionEnvelopeContract(
                packet_id="p1",
                world_state_features={"a": 1.0},
                advisory_features={"b": 2.0},
                explanation_lines=("x",),
                metadata={},
            )
        )
    )
    assert "external_world_state_features" in enrichment
    assert "external_packet_id" in enrichment
