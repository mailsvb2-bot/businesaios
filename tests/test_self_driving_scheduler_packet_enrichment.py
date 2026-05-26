from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.recommendation_packet_contract import RecommendationPacketContract
from contracts.decisioning.world_state_contract import WorldStateContract
from runtime.integration.decision_input_packet import DecisionInputPacket
from runtime.self_driving_scheduler import tick_once


@dataclass
class _Ws:
    timestamp_ms: int
    safe_mode: bool
    meta: dict
    deployment_proposal: dict


class _Learning:
    def maybe_propose_deployment(self):
        return {"kind": "deploy", "candidate_policy_id": "p1", "rollout_pct": 10}

    def build_deploy_world_state(self, proposal):
        return _Ws(timestamp_ms=123, safe_mode=False, meta={}, deployment_proposal=dict(proposal))


class _DecisionCore:
    def issue(self, state):
        return {"state_meta": dict(getattr(state, "meta", {}) or {})}


class _ExecRes:
    ok = True
    decision_id = "d1"


class _Executor:
    def execute(self, env):
        _ = env
        return _ExecRes()


class _Provider:
    def build_decision_input_packet(self, *, world_state, proposal, generated_at_ms, safe_mode):
        _ = (world_state, proposal, generated_at_ms, safe_mode)
        return DecisionInputPacket(
            recommendation_packet=RecommendationPacketContract(
                packet_id="packet-1",
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


def test_self_driving_scheduler_accepts_optional_packet_provider() -> None:
    res = tick_once(
        learning_system=_Learning(),
        decision_core=_DecisionCore(),
        executor=_Executor(),
        decision_input_provider=_Provider(),
    )
    assert res.ok is True
