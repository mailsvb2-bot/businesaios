from dataclasses import dataclass

from demand_decision.demand_decision_candidate_builder import DemandDecisionCandidateBuilder


@dataclass
class Candidate:
    rank_score: object


def test_candidate_builder_skips_malformed_rank_scores_without_crashing():
    builder = DemandDecisionCandidateBuilder()
    result = builder.build({"ranked_candidates": [Candidate("bad"), Candidate(0.5)]})
    assert len(result) == 1
    assert result[0].rank_score == 0.5
