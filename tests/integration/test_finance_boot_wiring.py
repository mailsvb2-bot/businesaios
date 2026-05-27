from __future__ import annotations

from runtime.boot.finance_boot import (
    StrategicFinanceRuntime,
    build_finance_runtime,
    register_finance_events,
    register_finance_jobs,
)


def test_finance_boot_wiring_uses_single_runtime_singleton() -> None:
    first = build_finance_runtime()
    second = build_finance_runtime()
    assert isinstance(first, StrategicFinanceRuntime)
    assert first is second
    assert first.finance_advisory_service is first.service


def test_finance_boot_registers_jobs_and_events() -> None:
    jobs: dict[str, object] = {}
    events: dict[str, object] = {}
    register_finance_jobs(jobs)
    register_finance_events(events)
    assert sorted(jobs) == [
        'finance.run_allocation_rebalance',
        'finance.run_forecast',
        'finance.run_scenario_evaluation',
    ]
    assert sorted(events) == [
        'finance.allocation_recommended',
        'finance.forecast_revised',
        'finance.scenario_selected',
    ]
