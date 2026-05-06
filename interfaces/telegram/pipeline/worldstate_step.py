from __future__ import annotations

from typing import Any, Dict
from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import build_world_state_for_telegram


def build_worldstate(*, event_log: Any, ctx: Any, tenant_id: str, enrich: Dict[str, Any], resolved_product: Dict[str, Any], now_ms: int):
    return build_world_state_for_telegram(
        event_store=event_log,
        ctx=ctx,
        tenant_id=tenant_id,
        user_timezone=str((enrich.get("settings") or {}).get("timezone") or "Europe/Amsterdam"),
        economy={"payments": enrich.get("payments", {}), "entitlements": enrich.get("entitlements", {})},
        entitlements=enrich.get("entitlements"),
        product_context=resolved_product,
        limit=800,
        now_ms=now_ms,
    )
