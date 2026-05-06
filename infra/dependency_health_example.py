from __future__ import annotations

from infra.dependency_health import (
    DependencyHealthCheck,
    run_dependency_health_checks,
)
from infra.readiness_gates import ReadinessGateResult, evaluate_readiness_gates


def example_dependency_readiness() -> dict:
    results = run_dependency_health_checks(
        [
            DependencyHealthCheck(name="config_loaded", probe=lambda: True),
            DependencyHealthCheck(name="telegram_sdk_available", probe=lambda: True),
        ]
    )

    gates = [
        ReadinessGateResult(
            name=item.name,
            passed=item.status == "ok",
        )
        for item in results
    ]
    return evaluate_readiness_gates(gates)
