from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.decision_gateway import issue_runtime_decision
from runtime.integration.decision_input_packet import DecisionInputPacket


class _Issuer:
    def __init__(self) -> None:
        self.calls = []
        self.envelope = SimpleNamespace(
            decision=SimpleNamespace(
                decision_id="decision-1",
                correlation_id="correlation-1",
            )
        )

    def issue(self, state):
        self.calls.append(state)
        return self.envelope


def test_issue_runtime_decision_routes_through_protocol() -> None:
    issuer = _Issuer()
    state = {"x": 1}
    out = issue_runtime_decision(issuer=issuer, state=state)
    assert out is issuer.envelope
    assert issuer.calls == [state]


def test_issue_runtime_decision_enriches_state_from_packet() -> None:
    issuer = _Issuer()
    state = {"x": 1, "meta": {}}
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
            explanation_lines=("line",),
        )
    )
    out = issue_runtime_decision(
        issuer=issuer,
        state=state,
        decision_input_packet=packet,
    )
    assert out is issuer.envelope
    issued_state = issuer.calls[-1]
    assert "meta" in issued_state
    assert issued_state["meta"]["external_packet_id"] == "p1"
    assert "external_world_state_features" in issued_state["meta"]


def test_issue_runtime_decision_rejects_forbidden_packet_fields() -> None:
    issuer = _Issuer()
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
            recommendations=(
                {"winner": "creative_1"},
            ),
            explanation_lines=(),
        )
    )
    with pytest.raises(RuntimeError):
        issue_runtime_decision(
            issuer=issuer,
            state={"x": 1, "meta": {}},
            decision_input_packet=packet,
        )
    assert issuer.calls == []
