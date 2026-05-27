from __future__ import annotations

from typing import Iterable, Protocol

from kernel.decision_candidate import DecisionCandidate


class CandidatePolicy(Protocol):
    def evaluate(self, candidate: DecisionCandidate) -> tuple[bool, str]: ...


class PolicyEvaluator:
    def evaluate(self, candidate: DecisionCandidate, policies: Iterable[CandidatePolicy]) -> tuple[bool, list[str]]:
        violations: list[str] = []
        for policy in policies:
            ok, reason = policy.evaluate(candidate)
            if not ok:
                violations.append(reason)
        return not violations, violations
