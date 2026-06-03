from __future__ import annotations

from typing import Callable
from collections.abc import Iterable

from ..action_context import SafetyActionContext
from .models import SandboxOutcome


class PredicateSandboxExecutor:
    def __init__(self, predicates: Iterable[Callable[[SafetyActionContext], str | None]] = ()):
        self._predicates = tuple(predicates)

    def run(self, ctx: SafetyActionContext) -> SandboxOutcome:
        findings: list[str] = []
        for predicate in self._predicates:
            result = predicate(ctx)
            if result:
                findings.append(str(result))
        return SandboxOutcome(passed=not findings, findings=tuple(findings), evidence={"checks": len(self._predicates)})
