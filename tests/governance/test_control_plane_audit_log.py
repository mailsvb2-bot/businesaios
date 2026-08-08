from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog


def test_persistent_governance_audit_log_appends_jsonl(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = PersistentGovernanceAuditLog(path)
    log.append(GovernanceAuditEvent(event_type="approval_requested", tenant_id="tenant-a", emitted_at=datetime.now(UTC), payload={"approval_id": "ap-1", "status": "requested"}))
    log.append(GovernanceAuditEvent(event_type="approval_decision_recorded", tenant_id="tenant-a", emitted_at=datetime.now(UTC), payload={"approval_id": "ap-1", "status": "approved"}))

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    assert rows[0]["event_type"] == "approval_requested"
    assert rows[1]["event_type"] == "approval_decision_recorded"
    log.validate_chain()


def test_multiple_audit_log_owners_keep_one_hash_chain(tmp_path) -> None:
    path = tmp_path / "shared_audit.jsonl"
    logs = (PersistentGovernanceAuditLog(path), PersistentGovernanceAuditLog(path))

    def append(index: int) -> None:
        logs[index % 2].append(GovernanceAuditEvent(
            event_type="approval_event",
            tenant_id="tenant-a",
            emitted_at=datetime.now(UTC),
            payload={"index": index},
        ))

    with ThreadPoolExecutor(max_workers=8) as executor:
        tuple(executor.map(append, range(40)))

    events = logs[0].read_events()
    assert len(events) == 40
    assert {int(event["payload"]["index"]) for event in events} == set(range(40))
    logs[0].validate_chain()
    assert logs[1].integrity_summary()["valid"] is True
