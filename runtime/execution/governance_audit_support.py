from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog


def _governance_audit_log(executor: Any, guard: Any | None = None):
    """Return the single audit sink already owned by the canonical runtime graph."""

    approval_gate = getattr(executor, "_approval_execution_gate", None)
    guard_workflow = getattr(guard, "_approval_workflow", None) if guard is not None else None
    gate_workflow = getattr(approval_gate, "_approval_workflow", None) if approval_gate is not None else None

    candidates = (
        getattr(guard, "_audit_log", None) if guard is not None else None,
        getattr(approval_gate, "_audit_log", None) if approval_gate is not None else None,
        getattr(guard_workflow, "_audit_log", None) if guard_workflow is not None else None,
        getattr(gate_workflow, "_audit_log", None) if gate_workflow is not None else None,
        getattr(executor, "_governance_audit_log", None),
    )
    for audit_log in candidates:
        if audit_log is not None and hasattr(audit_log, "append"):
            return audit_log

    audit_log = PersistentGovernanceAuditLog()
    executor._governance_audit_log = audit_log
    return audit_log


def _append_governance_audit(
    *,
    executor: Any,
    event: GovernanceAuditEvent | None = None,
    guard: Any | None = None,
    tenant_id: str | None = None,
    event_type: str | None = None,
    payload: Mapping[str, object] | None = None,
) -> None:
    """Append best-effort governance evidence without creating decision authority."""

    try:
        audit_event = event
        if audit_event is None:
            audit_event = GovernanceAuditEvent(
                event_type=str(event_type or "").strip(),
                tenant_id=str(tenant_id or "").strip() or "unknown",
                payload=dict(payload or {}),
            )
        _governance_audit_log(executor, guard=guard).append(audit_event)
    except Exception:
        return


__all__ = ["_append_governance_audit", "_governance_audit_log"]
