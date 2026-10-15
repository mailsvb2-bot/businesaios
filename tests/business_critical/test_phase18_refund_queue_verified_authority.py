"""Refund queue execution must use only a server-injected commercial verifier."""
from __future__ import annotations

import pytest

from interfaces.telegram.runtime_loops.payment_jobs import PaymentJobsConfig, PaymentJobsLoop


class Outbox:
    def __init__(self, event="refund.succeeded"):
        self.pending = [{
            "id": "job-r1", "attempts": 0,
            "payload": {"type": "yookassa_webhook", "payload": {
                "event": event, "object": {
                    "id": "refund-1", "payment_id": "payment-1",
                },
            }},
        }]
        self.delivered = []
        self.retried = []

    def list_pending(self, *, limit):
        return list(self.pending)

    def claim(self, job_id):
        return True

    def mark_delivered(self, job_id):
        self.delivered.append(job_id)

    def schedule_retry(self, job_id, *, after_ms, error):
        self.retried.append((job_id, error))


@pytest.mark.parametrize("outcome", [True, False, None])
def test_refund_requires_positive_server_verification(outcome):
    outbox = Outbox()
    seen = []

    def reconcile(payload):
        seen.append(payload)
        return outcome

    worker = PaymentJobsLoop(
        decide_fn=lambda *_: pytest.fail("legacy decision must not run"),
        execute_fn=lambda *_: pytest.fail("legacy executor must not run"),
        commercial_reconcile_fn=reconcile, payment_outbox=outbox,
        cfg=PaymentJobsConfig(every_ms=1),
    )
    worker.tick()
    assert len(seen) == 1
    assert seen[0]["refund_id"] == "refund-1"
    assert seen[0]["external_id"] == "payment-1"
    assert outbox.delivered == (["job-r1"] if outcome is True else [])
    assert bool(outbox.retried) is (outcome is not True)


def test_refund_verifier_exception_never_acknowledges_event():
    outbox = Outbox()

    def fail(_):
        raise RuntimeError("merchant_api_unavailable")

    worker = PaymentJobsLoop(
        decide_fn=lambda *_: pytest.fail("legacy path"),
        execute_fn=lambda *_: pytest.fail("legacy path"),
        commercial_reconcile_fn=fail, payment_outbox=outbox,
        cfg=PaymentJobsConfig(every_ms=1),
    )
    worker.tick()
    assert not outbox.delivered
    assert len(outbox.retried) == 1
    assert "merchant_api_unavailable" in outbox.retried[0][1]
