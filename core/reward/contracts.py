from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from application.decisioning.candidate_collection import CandidateCollection
from application.decisioning.candidate_observations import CandidateObservationSet


@dataclass(frozen=True)
class RewardObservationContext:
    tenant_id: str
    correlation_id: str
    candidates: CandidateCollection


class RewardObserverPort(Protocol):
    def observe(self, context: RewardObservationContext) -> CandidateObservationSet:
        ...
