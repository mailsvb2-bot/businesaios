from __future__ import annotations

from typing import Any

from core.finance.strategic.events.allocation_recommended import AllocationRecommended
from core.finance.strategic.events.forecast_revised import ForecastRevised
from core.finance.strategic.events.scenario_selected import ScenarioSelected


def persist_runtime_artifacts(
    *,
    forecast_repository,
    scenario_repository,
    allocation_repository,
    decision_audit_repository,
    publish_runtime_event,
    finance_input,
    forecast_version: str,
    advisory: Any,
    payload: dict[str, Any],
) -> None:
    key = f"{finance_input.tenant_id}:{finance_input.correlation_id}"
    forecast_event = ForecastRevised(forecast_version=forecast_version, summary=payload["explanations"]["scenario"])
    scenario_event = ScenarioSelected(scenario_name=advisory.selected_scenario)
    allocation_event = AllocationRecommended(allocations=advisory.channel_allocation)
    forecast_repository.save(key, forecast_event)
    scenario_repository.save(key, scenario_event)
    allocation_repository.save(key, allocation_event)
    decision_audit_repository.save(key, payload)
    publish_runtime_event(
        "finance.forecast_revised",
        finance_input,
        {"forecast_version": forecast_version, "selected_scenario": advisory.selected_scenario},
    )
    publish_runtime_event(
        "finance.scenario_selected",
        finance_input,
        {"scenario_name": advisory.selected_scenario, "guard_codes": list(advisory.guard_codes)},
    )
    publish_runtime_event(
        "finance.allocation_recommended",
        finance_input,
        {
            "allocations": {name: str(value) for name, value in advisory.channel_allocation.items()},
            "liquidity_mode": advisory.liquidity_mode,
        },
    )
