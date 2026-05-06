from __future__ import annotations

from runtime.boot.finance_boot import build_finance_runtime
from tests.test_finance_canon_integration_v27 import _snapshot


def test_finance_decision_payload_contains_trace_bundle() -> None:
    runtime = build_finance_runtime()
    decision = runtime.service.evaluate(runtime.build_financial_input({
        "tenant_id": "tenant-obs",
        "correlation_id": "corr-obs",
        "economics_snapshot": _snapshot(),
    }))
    traces = decision.decision_payload["traces"]
    trace_types = {item["trace_type"] for item in traces}
    assert "strategic_finance.forecast" in trace_types
    assert "strategic_finance.scenario" in trace_types
    assert "strategic_finance.allocation" in trace_types
    assert "strategic_finance.risk" in trace_types
