from __future__ import annotations

from collections.abc import Callable

from runtime.boot.finance_boot import StrategicFinanceRuntime, register_finance_runtime


def run_forecast_job(
    raw: dict,
    runtime_provider: Callable[[], StrategicFinanceRuntime] | None = None,
) -> str:
    runtime = register_finance_runtime(host_runtime_provider=runtime_provider)
    return runtime.run_forecast(raw)
