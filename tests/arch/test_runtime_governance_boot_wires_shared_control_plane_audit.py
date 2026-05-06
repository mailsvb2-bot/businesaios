from __future__ import annotations

from pathlib import Path


def test_runtime_governance_boot_uses_shared_persistent_control_plane_audit() -> None:
    text = Path("runtime/boot/governance_execution_boot.py").read_text(encoding="utf-8")
    assert "audit_log = PersistentGovernanceAuditLog()" in text
    assert "PersistentTenantPolicyOverrideRegistry(audit_log=audit_log)" in text
    assert "PersistentKillSwitchRegistry(audit_log=audit_log)" in text
    assert "ApprovalWorkflow(" in text and "audit_log=audit_log" in text
