from __future__ import annotations

from collections.abc import Callable

from runtime.boot.finance_boot_runtime import StrategicFinanceRuntime, build_finance_runtime


def run_forecast_job(
    raw: dict,
    runtime_provider: Callable[[], StrategicFinanceRuntime] | None = None,
) -> str:
    runtime = runtime_provider() if runtime_provider is not None else build_finance_runtime()
    return runtime.run_forecast(raw)
