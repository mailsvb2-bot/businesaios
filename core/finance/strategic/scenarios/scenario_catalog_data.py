from __future__ import annotations

from config.strategic_finance_scenario_policy import DEFAULT_STRATEGIC_FINANCE_SCENARIOS
from core.finance.strategic.types import Scenario


def scenario_definitions() -> tuple[Scenario, ...]:
    return DEFAULT_STRATEGIC_FINANCE_SCENARIOS
