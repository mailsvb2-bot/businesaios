from __future__ import annotations

from observability.action_audit_log import FileActionAuditLog
from observability.audit_storage_policy import AuditStoragePolicy
from observability.decision_audit_log import FileDecisionAuditLog


def test_action_audit_log_compacts_and_rotates(tmp_path) -> None:
    log = FileActionAuditLog(path=tmp_path / 'action.json')
    log.storage_policy = AuditStoragePolicy(max_records=2, max_bytes=1, backup_count=1)
    for idx in range(3):
        log.record({'tenant_id': 'tenant-a', 'action_id': f'a-{idx}', 'payload': {'n': idx}})
    assert len(log.records) == 2
    assert (tmp_path / 'action.json.1').exists()


def test_decision_audit_log_compacts_and_rotates(tmp_path) -> None:
    log = FileDecisionAuditLog(path=tmp_path / 'decision.json')
    log.storage_policy = AuditStoragePolicy(max_records=2, max_bytes=1, backup_count=1)
    for idx in range(3):
        log.record_payload({'decision_id': f'd-{idx}', 'trace_id': f't-{idx}'})
    assert len(log.records) == 2
    assert (tmp_path / 'decision.json.1').exists()
