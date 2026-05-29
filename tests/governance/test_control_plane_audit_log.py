from __future__ import annotations

import json
from datetime import datetime, timezone, UTC

from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog


def test_persistent_governance_audit_log_appends_jsonl(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = PersistentGovernanceAuditLog(path)
    log.append(
        GovernanceAuditEvent(
            event_type="approval_requested",
            tenant_id="tenant-a",
            emitted_at=datetime.now(UTC),
            payload={"approval_id": "ap-1", "status": "requested"},
        )
    )
    log.append(
        GovernanceAuditEvent(
            event_type="approval_decision_recorded",
            tenant_id="tenant-a",
            emitted_at=datetime.now(UTC),
            payload={"approval_id": "ap-1", "status": "approved"},
        )
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    assert rows[0]["event_type"] == "approval_requested"
    assert rows[1]["event_type"] == "approval_decision_recorded"
