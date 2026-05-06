from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class DependencyHealthCheck:
    name: str
    probe: Callable[[], bool]


@dataclass(frozen=True)
class DependencyHealthResult:
    name: str
    status: str
    details: dict = field(default_factory=dict)


def run_dependency_health_checks(
    checks: list[DependencyHealthCheck],
) -> tuple[DependencyHealthResult, ...]:
    results: list[DependencyHealthResult] = []

    for check in checks:
        ok = check.probe()
        results.append(
            DependencyHealthResult(
                name=check.name,
                status="ok" if ok else "failed",
            )
        )

    return tuple(results)
