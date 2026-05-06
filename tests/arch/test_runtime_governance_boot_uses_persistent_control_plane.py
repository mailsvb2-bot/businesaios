from __future__ import annotations

from pathlib import Path


def test_runtime_governance_boot_uses_persistent_control_plane() -> None:
    text = Path("runtime/boot/governance_execution_boot.py").read_text(encoding="utf-8")
    assert "PersistentApprovalStore" in text
    assert "PersistentKillSwitchRegistry" in text
    assert "PersistentTenantPolicyOverrideRegistry" in text
    assert "CANON_BOOT_WIRING_ONLY = True" in text
