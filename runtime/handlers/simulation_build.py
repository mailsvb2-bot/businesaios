from __future__ import annotations

from runtime.simulation import ScenarioInput, build_named_scenario

CANON_THIN_HANDLER = True

def handle_simulation_build(tenant_id: str, scenario_name: str) -> ScenarioInput:
    return build_named_scenario(tenant_id=tenant_id, scenario_name=scenario_name)
