from __future__ import annotations

from dataclasses import dataclass

import pytest

from application.decision_policy.policy_stage import propose_action


@dataclass
class Proposal:
    action: str
    payload: dict


class Trace:
    def __init__(self):
        self.steps = []

    def try_add_step(self, **kwargs):
        self.steps.append(kwargs)


class BrokenPolicy:
    id = "broken"

    def propose_many(self, state):
        raise ValueError("boom")

    def propose(self, state):
        return Proposal(action="noop@v1", payload={})


class FallbackPolicy(BrokenPolicy):
    allow_rank_fallback = True


def test_rank_stage_is_fail_closed_by_default():
    with pytest.raises(RuntimeError):
        propose_action(policy=BrokenPolicy(), state={}, trace=Trace())


def test_rank_stage_can_fallback_when_explicitly_allowed():
    out = propose_action(policy=FallbackPolicy(), state={}, trace=Trace())
    assert out.action == "noop@v1"


class RankedPolicy:
    def propose_many(self, state):
        return [
            type(
                "Ranked",
                (),
                {
                    "action": "noop@v1",
                    "payload": {},
                    "ranking": {
                        "expected_profit_delta_minor": 10.0,
                        "guard_value:spend-cap": 40_000.0,
                    },
                },
            )()
        ]


def test_rank_stage_preserves_decision_only_guard_metadata():
    out = propose_action(policy=RankedPolicy(), state={}, trace=Trace())
    assert out.action == "noop@v1"
    assert out.payload == {}
    assert out.ranking["guard_value:spend-cap"] == 40_000.0


class MutableRankedPolicy:
    def propose_many(self, state):
        proposal = Proposal(action="noop@v1", payload={})
        proposal.ranking = {
            "expected_profit_delta_minor": 1.0,
            "guard_value:spend-cap": 30_000.0,
        }
        return [proposal]


def test_rank_stage_preserves_mutable_legacy_proposal_type_and_guard_metadata():
    out = propose_action(policy=MutableRankedPolicy(), state={}, trace=Trace())
    assert isinstance(out, Proposal)
    assert out.ranking["guard_value:spend-cap"] == 30_000.0
