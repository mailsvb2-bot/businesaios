from __future__ import annotations

from application.decisioning.candidate_collection import CandidateCollection
from application.decisioning.candidate_observations import CandidateObservationSet
from application.decisioning.candidate_scores import CandidateScoreSet
from kernel.decisioning.candidate_types import CandidateEnvelope, CandidateObservation, CandidateScore


def test_candidate_collection_from_iterable() -> None:
    coll = CandidateCollection.from_iterable([
        CandidateEnvelope(candidate_id="c1", candidate_kind="kind", payload={"x": 1}),
    ])
    assert coll.is_empty() is False
    assert coll.items[0].candidate_id == "c1"


def test_candidate_score_set_from_iterable() -> None:
    score_set = CandidateScoreSet.from_iterable([
        CandidateScore(candidate_id="c1", score_name="s", score_value=1.0, explanation="ok"),
    ])
    assert score_set.items[0].score_value == 1.0


def test_candidate_observation_set_from_iterable() -> None:
    obs_set = CandidateObservationSet.from_iterable([
        CandidateObservation(candidate_id="c1", observation_name="o", observation_value="v", details={}),
    ])
    assert obs_set.items[0].observation_value == "v"
