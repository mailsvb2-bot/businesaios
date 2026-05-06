from __future__ import annotations

from tests.test_finance_canon_integration_v27 import _snapshot
from runtime.boot.finance_boot import build_finance_runtime


def test_strategic_finance_runtime_flow_persists_runtime_artifacts() -> None:
    runtime = build_finance_runtime()
    raw = {
        'tenant_id': 'tenant-1',
        'correlation_id': 'corr-1',
        'economics_snapshot': _snapshot(),
    }
    decision = runtime.service.evaluate(runtime.build_financial_input(raw))
    audit = runtime.decision_audit_repository.get('tenant-1:corr-1')
    assert decision.decision_payload['advisory_only'] is True
    assert audit is not None
    assert runtime.forecast_repository.get('tenant-1:corr-1') is not None
    assert runtime.scenario_repository.get('tenant-1:corr-1') is not None
    assert runtime.allocation_repository.get('tenant-1:corr-1') is not None
