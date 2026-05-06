from __future__ import annotations

from typing import Any

from observability.finance.allocation_trace import allocation_trace
from observability.finance.forecast_trace import forecast_trace
from observability.finance.risk_signal_trace import risk_signal_trace
from observability.finance.scenario_trace import scenario_trace


def build_trace_bundle(*, finance_input, forecast_version: str, advisory: Any) -> list[dict[str, Any]]:
    trace_id = f"{finance_input.tenant_id}:{finance_input.correlation_id}"
    source_snapshot_id = finance_input.metadata.get("economics_snapshot_id")
    traces: list[dict[str, Any]] = [
        forecast_trace(trace_id, forecast_version, source_snapshot_id=source_snapshot_id),
        scenario_trace(trace_id, advisory.selected_scenario, source_snapshot_id=source_snapshot_id),
        allocation_trace(trace_id, len(advisory.channel_allocation), source_snapshot_id=source_snapshot_id),
    ]
    for code in advisory.guard_codes:
        traces.append(risk_signal_trace(trace_id, code, source_snapshot_id=source_snapshot_id))
    return traces
