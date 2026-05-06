from __future__ import annotations
from runtime.ads import AutopilotTarget
from runtime.tenancy import normalize_tenant_id

async def ads_autopilot_tick(sys) -> None:
    scheduler = getattr(sys, "autopilot_scheduler", None)
    if scheduler is None:
        return

    tenants = []
    registry = getattr(sys, "tenant_registry", None)
    if registry is not None:
        try:
            tenants = [normalize_tenant_id(t.tenant_id) for t in registry.list_active_tenants()]
            tenants = [t for t in tenants if t]
        except Exception:
            tenants = []
    if not tenants:
        fallback_tenant = normalize_tenant_id(getattr(sys, "default_tenant_id", None))
        tenants = [fallback_tenant] if fallback_tenant else []

    token_store = getattr(sys, "ads_tokens", None)
    for tid in tenants:
        tid = str(tid)
        if not tid:
            continue
        accounts = []
        if token_store is not None:
            try:
                accounts = await token_store.list_connected_accounts(tenant_id=tid)
            except Exception:
                accounts = []
        if accounts:
            for acc in accounts:
                await scheduler.tick(target=AutopilotTarget(tenant_id=tid, platform=str(acc.platform), account_id=str(acc.account_id), notify_chat_id=None))
        else:
            continue
