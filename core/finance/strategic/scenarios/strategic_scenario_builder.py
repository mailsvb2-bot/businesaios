from __future__ import annotations

from core.finance.strategic.scenarios.scenario_catalog import ScenarioCatalog


class StrategicScenarioBuilder:
    """Canonical scenario builder for the strategic finance contour."""

    def build(self):
        return ScenarioCatalog().build()
