from __future__ import annotations

from dataclasses import dataclass

import pytest

from application.decision_policy.policy_stage import propose_action
from core.policies.telegram.helpers import normalize_proposed_action


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


@dataclass(frozen=True)
class FrozenRankedProposal:
    action: str
    payload: dict
    ranking: dict


class MixedProposalTypesPolicy:
    def propose_many(self, state):
        return [
            Proposal(action="noop@v1", payload={}),
            FrozenRankedProposal(
                action="noop@v1",
                payload={},
                ranking={
                    "expected_profit_delta_minor": 100.0,
                    "guard_value:spend-cap": 25_000.0,
                },
            ),
        ]


def test_rank_stage_materializes_the_actual_selected_candidate_type():
    out = propose_action(policy=MixedProposalTypesPolicy(), state={}, trace=Trace())
    assert isinstance(out, FrozenRankedProposal)
    assert out.ranking["guard_value:spend-cap"] == 25_000.0


def test_mapping_proposal_normalization_preserves_decision_only_ranking():
    out = normalize_proposed_action({
        "action": "noop@v1",
        "payload": {},
        "ranking": {
            "expected_profit_delta_minor": 5.0,
            "guard_value:spend-cap": 20_000,
        },
    })
    assert out.payload == {}
    assert out.ranking["guard_value:spend-cap"] == 20_000.0


_OBJECTIVE_DIMENSIONS = (
    "business_value",
    "revenue",
    "margin",
    "cash_flow",
    "risk",
    "customer_impact",
    "cost",
    "strategic_value",
)


def _objective_ranking(value: float, *, expected_profit: float) -> dict[str, float]:
    return {
        "expected_profit_delta_minor": expected_profit,
        **{f"objective:{dimension}": value for dimension in _OBJECTIVE_DIMENSIONS},
    }


class MultiObjectivePolicy:
    def propose_many(self, state):
        return [
            FrozenRankedProposal(
                action="noop@v1",
                payload={"choice": "single-kpi"},
                ranking=_objective_ranking(-0.4, expected_profit=1_000_000.0),
            ),
            FrozenRankedProposal(
                action="noop@v1",
                payload={"choice": "balanced"},
                ranking=_objective_ranking(0.6, expected_profit=0.0),
            ),
        ]


def test_multi_objective_mode_does_not_pick_single_kpi_profit_winner():
    trace = Trace()
    out = propose_action(policy=MultiObjectivePolicy(), state={}, trace=trace)
    assert out.payload["choice"] == "balanced"
    ranking_step = next(item for item in trace.steps if item["name"] == "rank_candidates")
    assert ranking_step["output"]["reason"].startswith("multi_objective:")


class IncompleteObjectivePolicy:
    def propose_many(self, state):
        return [
            FrozenRankedProposal(
                action="noop@v1",
                payload={},
                ranking={"objective:revenue": 0.5},
            )
        ]


def test_incomplete_multi_objective_projection_fails_closed():
    with pytest.raises(RuntimeError, match="DECISION_POLICY_STAGE_FAILED:objective_projection_invalid"):
        propose_action(policy=IncompleteObjectivePolicy(), state={}, trace=Trace())


class MixedLegacyAndObjectivePolicy:
    def propose_many(self, state):
        return [
            FrozenRankedProposal(
                action="noop@v1",
                payload={"choice": "legacy"},
                ranking={"expected_profit_delta_minor": 10_000_000.0},
            ),
            FrozenRankedProposal(
                action="noop@v1",
                payload={"choice": "objective"},
                ranking=_objective_ranking(0.2, expected_profit=0.0),
            ),
        ]


def test_objective_mode_excludes_legacy_single_kpi_candidate():
    out = propose_action(policy=MixedLegacyAndObjectivePolicy(), state={}, trace=Trace())
    assert out.payload["choice"] == "objective"
