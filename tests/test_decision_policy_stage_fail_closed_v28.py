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
