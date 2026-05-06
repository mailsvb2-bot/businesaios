from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_billing_scheduler_and_recovery_surfaces_stay_on_public_owner_paths() -> None:
    jobs_text = _read('billing/scheduler/jobs.py')
    queue_bridge_text = _read('billing/scheduler/queue_bridge.py')
    refund_text = _read('billing/refund_orchestrator.py')
    chargeback_text = _read('billing/chargeback_orchestrator.py')

    assert 'from billing.scheduler.lease import' in jobs_text
    assert 'from runtime.queue import' in queue_bridge_text
    assert 'from runtime.queue.job_' not in queue_bridge_text
    assert 'from runtime.queue._' not in queue_bridge_text
    assert 'from runtime.monetization import' in refund_text
    assert 'from runtime.monetization.contracts import' not in refund_text
    assert 'from runtime.monetization import' in chargeback_text
    assert 'from runtime.monetization.contracts import' not in chargeback_text
    assert 'from reliability.idempotency_' not in jobs_text
    assert 'from reliability.idempotency_' not in queue_bridge_text
    assert 'from reliability.idempotency_' not in refund_text
    assert 'from reliability.idempotency_' not in chargeback_text
