from __future__ import annotations

import json
from pathlib import Path

from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog
from governance.kill_switch_registry import KillSwitchEntry, PersistentKillSwitchRegistry, _utc_now
from governance.tenant_policy_overrides import PersistentTenantPolicyOverrideRegistry, TenantPolicyOverride


def test_control_plane_audit_log_builds_valid_hash_chain(tmp_path: Path) -> None:
    log = PersistentGovernanceAuditLog(tmp_path / "audit.jsonl")
    log.append(GovernanceAuditEvent(event_type="one", tenant_id="tenant-a", payload={"n": 1}))
    log.append(GovernanceAuditEvent(event_type="two", tenant_id="tenant-a", payload={"n": 2}))
    log.validate_chain()
    events = log.read_events()
    assert len(events) == 2
    assert events[0]["previous_hash"] == "GENESIS"
    assert events[1]["previous_hash"] == events[0]["record_hash"]


def test_persistent_kill_switch_registry_emits_audit_events(tmp_path: Path) -> None:
    log = PersistentGovernanceAuditLog(tmp_path / "audit.jsonl")
    registry = PersistentKillSwitchRegistry(tmp_path / "kill.json", audit_log=log)
    registry.activate(
        KillSwitchEntry(
            switch_id="sw-1",
            scope="tenant",
            scope_id="tenant-a",
            reason="incident",
            activated_by="security-1",
            activated_at=_utc_now(),
            metadata={"tenant_id": "tenant-a"},
        )
    )
    registry.release(scope="tenant", scope_id="tenant-a")
    events = log.read_events()
    assert [item["event_type"] for item in events] == ["kill_switch_activated", "kill_switch_released"]
    log.validate_chain()


def test_persistent_tenant_override_registry_emits_audit_events(tmp_path: Path) -> None:
    log = PersistentGovernanceAuditLog(tmp_path / "audit.jsonl")
    registry = PersistentTenantPolicyOverrideRegistry(tmp_path / "overrides.json", audit_log=log)
    registry.put(TenantPolicyOverride(tenant_id="tenant-a", blocked_categories=frozenset({"outbound"})))
    registry.remove("tenant-a")
    events = log.read_events()
    assert [item["event_type"] for item in events] == [
        "tenant_policy_override_upserted",
        "tenant_policy_override_removed",
    ]
    log.validate_chain()
