from __future__ import annotations

from types import SimpleNamespace

from runtime.boot.finance_boot import register_finance_routes


def test_register_finance_routes_attaches_state_metadata() -> None:
    app = SimpleNamespace()
    register_finance_routes(app)
    assert app.state.finance_runtime is not None
    assert "finance.run_forecast" in app.state.finance_job_registry
    assert "finance.forecast_revised" in app.state.finance_event_registry


def test_register_finance_routes_supports_mapping_shell() -> None:
    app: dict[str, object] = {}
    result = register_finance_routes(app)
    assert result is app
    assert app["finance_runtime"] is not None
    assert "finance.run_allocation_rebalance" in app["finance_job_registry"]
