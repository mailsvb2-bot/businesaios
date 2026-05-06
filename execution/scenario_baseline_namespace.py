from __future__ import annotations

from dataclasses import dataclass

from execution.canonical_scenario_governance import canonical_scenario_namespace


CANON_HEADLESS_SCENARIO_BASELINE_NAMESPACE = True


@dataclass(frozen=True)
class ScenarioBaselineNamespace:
    """
    Produces stable baseline names per scenario.
    """

    prefix: str = "scenario"

    def name_for(self, *, scenario: str, suffix: str = "golden") -> str:
        payload = canonical_scenario_namespace(scenario=scenario, prefix=self.prefix, suffix=suffix)
        return str(payload.get('scenario_governance', {}).get('baseline_name') or '')


__all__ = [
    "CANON_HEADLESS_SCENARIO_BASELINE_NAMESPACE",
    "ScenarioBaselineNamespace",
]
