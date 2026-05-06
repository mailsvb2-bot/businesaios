from __future__ import annotations

from runtime.jobs.run_allocation_rebalance_job import run_allocation_rebalance_job
from runtime.jobs.run_forecast_job import run_forecast_job
from runtime.jobs.run_scenario_evaluation_job import run_scenario_evaluation_job


def test_finance_jobs_are_importable_and_callable() -> None:
    assert callable(run_forecast_job)
    assert callable(run_scenario_evaluation_job)
    assert callable(run_allocation_rebalance_job)
