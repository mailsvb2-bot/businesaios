from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_billing_final_wave_surfaces_remain_on_canonical_paths() -> None:
    jobs_text = _read('billing/scheduler/jobs.py')
    queue_bridge_text = _read('billing/scheduler/queue_bridge.py')
    recon_text = _read('billing/reconciliation_service.py')

    assert 'from billing.reconciliation_service import BillingReconciliationService, ReconciliationReport' in jobs_text
    assert 'from billing.reconciliation_service import ReconciliationDrift' not in jobs_text
    assert 'from billing.commercial_cycle_contract import ReconciliationDrift' in jobs_text
    assert 'from runtime.queue import' in queue_bridge_text
    assert 'from runtime.queue.job_' not in queue_bridge_text
    assert 'from runtime.queue._' not in queue_bridge_text
    assert 'from runtime.monetization import' in recon_text
    assert 'from runtime.monetization.contracts import' not in recon_text
    assert 'from observability.tenant_metrics_registry import TenantMetricsRegistry' in recon_text
