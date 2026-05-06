from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult, Scenario


class ScenarioIntegrityGuard:
    def check(self, scenarios: tuple[Scenario, ...]) -> GuardResult:
        names = [item.name for item in scenarios]
        total = sum((item.probability for item in scenarios), start=Decimal("0"))
        ok = len(names) == len(set(names)) and Decimal("0.99") <= total <= Decimal("1.01")
        return GuardResult(ok=ok, code="SCENARIO_OK" if ok else "SCENARIO_FAIL", message="ok" if ok else "scenario probabilities invalid")
