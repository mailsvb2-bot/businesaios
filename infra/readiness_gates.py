from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReadinessGateResult:
    name: str
    passed: bool
    details: dict = field(default_factory=dict)


def evaluate_readiness_gates(results: list[ReadinessGateResult]) -> dict:
    overall = all(item.passed for item in results)
    return {
        "ready": overall,
        "gates": [
            {
                "name": item.name,
                "passed": item.passed,
                "details": dict(item.details),
            }
            for item in results
        ],
    }
