from __future__ import annotations

CANON_THIN_HANDLER = True


from typing import Any

from runtime.ads import bind_runtime_state, policy_store
from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

ACTION_NAME = "ads_rl_report@v1"


def handle_ads_rl_report(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    p = payload or {}
    bind_runtime_state(event_store=event_store)
    tenant_id = as_tenant_id(str(p.get("tenant_id") or ""))
    snap = policy_store.get_latest(tenant_id=str(tenant_id))
    if snap is None:
        return {
            "status": "ok",
            "tenant_id": str(tenant_id),
            "policy": None,
            "message": "no_policy",
        }
    return {
        "status": "ok",
        "tenant_id": str(tenant_id),
        "policy": {
            "policy_id": snap.policy_id,
            "version": snap.version,
            "created_ms": snap.created_ms,
            "params": dict(snap.params or {}),
        },
    }
