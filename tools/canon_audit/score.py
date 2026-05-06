from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonSubscores:
    functional_preservation: float
    ownership_uniqueness: float
    canonical_path_integrity: float
    governance_integrity: float
    evidence_integrity: float
    runtime_discipline: float
    proof_strength: float
    duplicate_authority_penalty: float
    hidden_logic_penalty: float
    compatibility_penalty: float
    god_module_penalty: float
    alternative_route_penalty: float
    fragility_penalty: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_raw_score_100(sub: CanonSubscores) -> float:
    positive_budget = 75.0
    negative_budget = 25.0
    positive = (
        18.0 * _clamp01(sub.functional_preservation)
        + 13.0 * _clamp01(sub.ownership_uniqueness)
        + 14.0 * _clamp01(sub.canonical_path_integrity)
        + 8.0 * _clamp01(sub.governance_integrity)
        + 8.0 * _clamp01(sub.evidence_integrity)
        + 7.0 * _clamp01(sub.runtime_discipline)
        + 7.0 * _clamp01(sub.proof_strength)
    )
    negative = (
        8.0 * _clamp01(sub.duplicate_authority_penalty)
        + 5.0 * _clamp01(sub.hidden_logic_penalty)
        + 4.0 * _clamp01(sub.compatibility_penalty)
        + 3.0 * _clamp01(sub.god_module_penalty)
        + 3.0 * _clamp01(sub.alternative_route_penalty)
        + 2.0 * _clamp01(sub.fragility_penalty)
    )
    normalized = (positive / positive_budget) * 100.0 - (negative / negative_budget) * 100.0
    return round(max(0.0, min(100.0, normalized)), 6)


def compute_admission_score_100(raw_score_100: float, hard_gates_passed: bool, has_violations: bool) -> float:
    if not hard_gates_passed or has_violations:
        return min(raw_score_100, 99.999999)
    return raw_score_100
