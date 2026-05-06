from __future__ import annotations

from application.decisioning.candidate_collection import CandidateCollection
from kernel.decisioning.candidate_types import CandidateEnvelope
from core.growth.contracts import GrowthScoringContext
from core.growth.service import GrowthService
from core.growth.simple_candidate_scorer import SimpleGrowthCandidateScorer
from core.reward.contracts import RewardObservationContext
from core.reward.reward_observer import RewardObserver
from core.reward.service import RewardService
from core.economics.candidate_scorer import EconomicsCandidateScorerImpl
from core.economics.contracts import EconomicsScoringContext
from core.ml.candidate_scorer import MlCandidateScorerImpl
from core.ml.contracts import MlScoringContext
from core.ml.service import MlService


def _candidates():
    return CandidateCollection.from_iterable([
        CandidateEnvelope(candidate_id="c1", candidate_kind="x", payload={"priority_score": 3.0, "profit_delta": 2.5, "expected_margin": 1.2, "model_score": 0.8}),
        CandidateEnvelope(candidate_id="c2", candidate_kind="x", payload={"priority_score": 1.0, "profit_delta": -1.0, "expected_margin": 0.2, "model_score": 0.4}),
    ])


def test_growth_service_scores_without_selecting_winner() -> None:
    service = GrowthService(SimpleGrowthCandidateScorer())
    out = service.score_candidates(GrowthScoringContext(tenant_id="t", correlation_id="c", candidates=_candidates()))
    assert len(out.items) == 2
    assert out.items[0].score_name == "growth_priority_score"


def test_reward_service_observes_without_narrowing() -> None:
    service = RewardService(RewardObserver())
    out = service.observe_candidates(RewardObservationContext(tenant_id="t", correlation_id="c", candidates=_candidates()))
    assert len(out.items) == 2
    assert out.items[0].observation_name == "profit_delta_observation"


def test_economics_candidate_scorer_scores_candidates() -> None:
    scorer = EconomicsCandidateScorerImpl()
    out = scorer.score(EconomicsScoringContext(tenant_id="t", correlation_id="c", candidates=_candidates()))
    assert len(out.items) == 2
    assert out.items[0].score_name == "expected_margin_score"


def test_ml_service_scores_candidates() -> None:
    service = MlService(MlCandidateScorerImpl())
    out = service.score_candidates(MlScoringContext(tenant_id="t", correlation_id="c", candidates=_candidates()))
    assert len(out.items) == 2
    assert out.items[0].score_name == "ml_model_score"
