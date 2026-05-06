from __future__ import annotations

from reliability.outbox_file_backend import FileOutboxBackend
from reliability.outbox_reconciliation import OutboxReconciliation
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage


def test_outbox_reconciliation_detects_digest_mismatch(tmp_path) -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'value': 1}))

    backend = FileOutboxBackend(tmp_path / 'backend')
    backend.deliver(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'value': 2}))

    report = OutboxReconciliation(outbox_store=store, backend=backend).reconcile_message(tenant_id='tenant-a', message_id='msg-1')
    codes = {finding.code for finding in report.findings}
    assert 'backend_delivered_but_store_not_finalized' in codes
    assert 'payload_digest_mismatch' in codes
