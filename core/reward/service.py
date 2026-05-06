from __future__ import annotations

from application.decisioning.candidate_observations import CandidateObservationSet
from core.reward.contracts import RewardObservationContext, RewardObserverPort


class RewardService:
    def __init__(self, observer: RewardObserverPort) -> None:
        self._observer = observer

    def observe_candidates(self, context: RewardObservationContext) -> CandidateObservationSet:
        return self._observer.observe(context)
