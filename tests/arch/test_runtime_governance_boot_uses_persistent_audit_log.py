from __future__ import annotations

from pathlib import Path


def test_runtime_governance_boot_uses_persistent_audit_log() -> None:
    text = Path("runtime/boot/governance_execution_boot.py").read_text(encoding="utf-8")
    assert "PersistentGovernanceAuditLog" in text
    assert "audit_log = PersistentGovernanceAuditLog()" in text
    assert "audit_log=audit_log" in text
