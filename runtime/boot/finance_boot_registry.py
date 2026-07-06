"""Finance boot: job specs, job registry, event registry."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping

from runtime.finance import AllocationRecommended, ForecastRevised, ScenarioSelected
from runtime.finance.job_spec import FinanceJobSpec

CANON_BOOT_WIRING_ONLY = True


def build_finance_job_specs() -> dict[str, FinanceJobSpec]:
    return {
        "finance.run_forecast": FinanceJobSpec(
            job_name="finance.run_forecast",
            purpose="build strategic finance forecast",
            runtime_phase="P70_POLICIES",
        ),
        "finance.run_scenario_evaluation": FinanceJobSpec(
            job_name="finance.run_scenario_evaluation",
            purpose="evaluate strategic finance scenarios",
            runtime_phase="P70_POLICIES",
        ),
        "finance.run_allocation_rebalance": FinanceJobSpec(
            job_name="finance.run_allocation_rebalance",
            purpose="rebalance strategic finance allocations",
            runtime_phase="P70_POLICIES",
        ),
    }


def register_finance_jobs(
    job_registry: MutableMapping[str, Callable[[dict], object]]
) -> MutableMapping[str, Callable[[dict], object]]:
    from runtime.jobs.run_allocation_rebalance_job import run_allocation_rebalance_job
    from runtime.jobs.run_forecast_job import run_forecast_job
    from runtime.jobs.run_scenario_evaluation_job import run_scenario_evaluation_job

    job_registry["finance.run_forecast"] = run_forecast_job
    job_registry["finance.run_scenario_evaluation"] = run_scenario_evaluation_job
    job_registry["finance.run_allocation_rebalance"] = run_allocation_rebalance_job
    return job_registry


def register_finance_events(
    event_registry: MutableMapping[str, type[object]]
) -> MutableMapping[str, type[object]]:
    event_registry["finance.forecast_revised"] = ForecastRevised
    event_registry["finance.scenario_selected"] = ScenarioSelected
    event_registry["finance.allocation_recommended"] = AllocationRecommended
    return event_registry


__all__ = [
    "build_finance_job_specs",
    "register_finance_jobs",
    "register_finance_events",
]
