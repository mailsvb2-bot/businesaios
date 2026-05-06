from __future__ import annotations

from threading import Lock
from typing import Any, Dict

from runtime.governance import PolicyUpdateGate, PolicyUpdateGateError
from runtime.tenancy import as_tenant_id

_POLICY_GATE: PolicyUpdateGate | None = None
_POLICY_GATE_LOCK = Lock()


def _policy_gate(*, event_store: Any | None) -> PolicyUpdateGate:
    global _POLICY_GATE
    with _POLICY_GATE_LOCK:
        if _POLICY_GATE is None:
            _POLICY_GATE = PolicyUpdateGate(cooldown_ms=5 * 60 * 1000)
        _POLICY_GATE.bind_event_store(event_store)
        return _POLICY_GATE


def ensure_autopilot_gate(*, payload: Dict[str, Any], event_store: Any | None, route: Any) -> tuple[str, str | None]:
    p = payload or {}
    tenant_id = as_tenant_id(str(p.get("tenant_id") or ""))
    gate = _policy_gate(event_store=event_store)
    update_id = str(getattr(route, "decision_id", "") or getattr(route, "correlation_id", "") or "tick")
    try:
        gate.propose(
            tenant_id=str(tenant_id),
            domain="ads.autopilot",
            update_id=update_id,
            payload={
                "decision_id": getattr(route, "decision_id", ""),
                "correlation_id": getattr(route, "correlation_id", ""),
                "issuer_id": getattr(route, "issuer_id", ""),
                "route": getattr(route, "route", ""),
            },
        )
        gate.approve(tenant_id=str(tenant_id), domain="ads.autopilot", update_id=update_id)
        gate.claim_for_apply(tenant_id=str(tenant_id), domain="ads.autopilot", update_id=update_id)
    except PolicyUpdateGateError as exc:
        return str(tenant_id), exc
    return str(tenant_id), None
