from __future__ import annotations

from ..contracts import ScenarioInput


def build_named_scenario(tenant_id: str, scenario_name: str) -> ScenarioInput:
    return ScenarioInput(tenant_id=tenant_id, scenario_name=scenario_name)
