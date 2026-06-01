from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional

from interfaces.telegram.parsing.telegram_context import TelegramContext, extract_telegram_user_id
from kernel.world_state import WorldStateV1


@dataclass(frozen=True)
class TelegramCompatOverlays:
    session: dict[str, Any]
    meta: dict[str, Any]
    product: dict[str, Any]
    economy: dict[str, Any]
    entitlements: dict[str, Any]
    user_id: str
    tenant_id: str
    timestamp_ms: int


def build_overlays_from_context(*, ctx: TelegramContext, now_ms: int | None = None, tenant_id: str = "default", user_timezone: str = "Europe/Amsterdam", economy: dict[str, Any] | None = None, entitlements: dict[str, Any] | None = None, product_context: dict[str, Any] | None = None) -> TelegramCompatOverlays:
    ts = int(now_ms if now_ms is not None else time.time() * 1000)
    session = {
        "channel": "telegram",
        "update_id": int(ctx.update_id),
        "message_id": ctx.message_id,
        "text": ctx.text,
        "command": ctx.command,
        "args": ctx.args,
        "is_callback": bool(ctx.is_callback),
        "callback_data": ctx.callback_data,
        "callback_query_id": ctx.callback_query_id,
    }
    meta = {
        "ingress": "telegram",
        "correlation_key": f"tg:{ctx.chat_id}:{ctx.update_id}",
        "user_timezone": str(user_timezone or "Europe/Amsterdam"),
    }
    econ = dict(economy or {})
    ent = dict(entitlements or {})
    econ.setdefault("entitlements", ent)
    product = dict(product_context or {})
    if not product:
        product = {
            "name": "BusinesAIOS Workspace",
            "domain": "organization_platform",
            "product_id": "organization_platform",
            "product_version": "v1",
            "modules": {"audio": True},
        }
    else:
        product.setdefault("name", "BusinesAIOS Workspace")
    uid = str(extract_telegram_user_id(ctx.raw) or ctx.chat_id)
    return TelegramCompatOverlays(
        session=session,
        meta=meta,
        product=product,
        economy=econ,
        entitlements=ent,
        user_id=uid,
        tenant_id=str(tenant_id or "default"),
        timestamp_ms=ts,
    )


def finalize_world_state(*, ws: WorldStateV1, overlays: TelegramCompatOverlays) -> WorldStateV1:
    return replace(
        ws,
        timestamp_ms=int(overlays.timestamp_ms),
        tenant_id=str(overlays.tenant_id),
        user_id=str(overlays.user_id),
    )
