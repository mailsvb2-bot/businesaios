from __future__ import annotations

from core.finance.strategic.scenarios.scenario_catalog_data import scenario_definitions
from core.finance.strategic.types import Scenario


class ScenarioCatalog:
    def build(self) -> tuple[Scenario, ...]:
        return scenario_definitions()
