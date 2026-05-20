from __future__ import annotations

from typing import Protocol

from runtime.demand_gravity.contracts import DemandCandidate
from runtime.demand_gravity.decision_input import DemandCandidateDecisionInput, build_decision_input
from runtime.demand_gravity.events import DemandGravityEventSink, candidate_submitted_event
from runtime.demand_gravity.validation import validate_demand_candidate


class DemandCandidateDecisionPort(Protocol):
    def ingest_demand_candidate(self, candidate: DemandCandidateDecisionInput) -> str:
        ...


class DemandGravityDecisionCoreBridge:
    def __init__(self, decision_core: DemandCandidateDecisionPort, *, event_sink: DemandGravityEventSink | None = None) -> None:
        self._decision_core = decision_core
        self._event_sink = event_sink

    def submit_candidates(self, candidates: tuple[DemandCandidate, ...]) -> tuple[str, ...]:
        refs: list[str] = []
        for candidate in candidates:
            validate_demand_candidate(candidate)
            decision_input = build_decision_input(candidate)
            decision_ref = self._decision_core.ingest_demand_candidate(decision_input)
            if self._event_sink is not None:
                self._event_sink.append(candidate_submitted_event(decision_input, decision_ref=decision_ref))
            refs.append(decision_ref)
        return tuple(refs)


__all__ = ["DemandCandidateDecisionPort", "DemandGravityDecisionCoreBridge"]
