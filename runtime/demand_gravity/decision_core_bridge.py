from __future__ import annotations

from typing import Protocol

from runtime.demand_gravity.contracts import DemandCandidate
from runtime.demand_gravity.validation import validate_demand_candidate


class DemandCandidateDecisionPort(Protocol):
    def ingest_demand_candidate(self, candidate: DemandCandidate) -> str:
        ...


class DemandGravityDecisionCoreBridge:
    def __init__(self, decision_core: DemandCandidateDecisionPort) -> None:
        self._decision_core = decision_core

    def submit_candidates(self, candidates: tuple[DemandCandidate, ...]) -> tuple[str, ...]:
        refs: list[str] = []
        for candidate in candidates:
            validate_demand_candidate(candidate)
            refs.append(self._decision_core.ingest_demand_candidate(candidate))
        return tuple(refs)
