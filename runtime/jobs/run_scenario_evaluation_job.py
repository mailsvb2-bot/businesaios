from __future__ import annotations

from typing import Callable

from runtime.boot.finance_boot import StrategicFinanceRuntime, register_finance_runtime


def run_scenario_evaluation_job(
    raw: dict,
    runtime_provider: Callable[[], StrategicFinanceRuntime] | None = None,
) -> dict:
    runtime = register_finance_runtime(host_runtime_provider=runtime_provider)
    return runtime.run_scenario_evaluation(raw)
