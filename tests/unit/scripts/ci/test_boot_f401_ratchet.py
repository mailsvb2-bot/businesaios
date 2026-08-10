from __future__ import annotations

from boot import observability_boot
from observability.action_audit_log import ActionAuditLog
from observability.decision_audit_log import DecisionAuditLog
from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT


def test_boot_f401_debt_cannot_regrow() -> None:
    assert ("boot", "F401") in _RATCHETED_STRICT_DEBT


def test_observability_boot_preserves_audit_log_compatibility_aliases() -> None:
    assert observability_boot.ActionAuditLog is ActionAuditLog
    assert observability_boot.DecisionAuditLog is DecisionAuditLog
