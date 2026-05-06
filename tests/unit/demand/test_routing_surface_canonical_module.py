from __future__ import annotations

from matching import RoutingCandidateBuilder, RoutingCandidateRanker
from matching.routing_surface import (
    RoutingCandidateBuilder as CanonicalRoutingCandidateBuilder,
    RoutingCandidateRanker as CanonicalRoutingCandidateRanker,
)
from contracts.matching.match_candidate import MatchCandidate


def test_matching_package_exports_canonical_routing_surface() -> None:
    assert RoutingCandidateBuilder is CanonicalRoutingCandidateBuilder
    assert RoutingCandidateRanker is CanonicalRoutingCandidateRanker


def test_routing_candidate_builder_preserves_previous_router_candidate_shape() -> None:
    candidate = MatchCandidate(
        business_id='b-1',
        score=1.75,
        score_breakdown={'fit': 1.75},
        reasons=('fit=1.750',),
        blocked=False,
    )
    built = RoutingCandidateBuilder().build(
        candidate=candidate,
        policy_tags=('fast:+0.2', 'fast:+0.2', '', 'guarded'),
        adjusted_score='2.5',
        blocked=False,
    )
    assert built.business_id == 'b-1'
    assert built.rank_score == 2.5
    assert built.policy_tags == ('fast:+0.2', 'guarded')
    assert built.trace == {'match_score': 1.75, 'adjusted_score': 2.5}
    assert built.blocked is False


def test_routing_candidate_ranker_orders_by_rank_score_and_blocked_state() -> None:
    ranker = RoutingCandidateRanker()
    first = RoutingCandidateBuilder().build(
        candidate=MatchCandidate(business_id='winner', score=1.0, blocked=False),
        policy_tags=(),
        adjusted_score=5.0,
        blocked=False,
    )
    second = RoutingCandidateBuilder().build(
        candidate=MatchCandidate(business_id='blocked-peer', score=1.0, blocked=True),
        policy_tags=(),
        adjusted_score=5.0,
        blocked=True,
    )
    ranked = ranker.rank((second, first))
    assert tuple(item.business_id for item in ranked) == ('winner', 'blocked-peer')
