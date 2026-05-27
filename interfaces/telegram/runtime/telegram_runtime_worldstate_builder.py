from __future__ import annotations

"""Telegram Runtime WorldState builder.

Canonical path for Telegram:

latest_events(...) -> build_world_state_from_events(...) -> compat overlays

Rules:
- WorldState is derived via reducers (event-sourced) only.
- Telegram-specific UX data is added as overlays.
- No alternative builder paths. This module is the single runtime entry point.
"""

import time
from typing import Any, Dict, List, Optional

from core.read_model.world_state_builder import build_world_state_from_events
from interfaces.telegram.parsing.telegram_context import TelegramContext
from interfaces.telegram.runtime.worldstate_causal import apply_causal_overlay
from interfaces.telegram.runtime.worldstate_overlays import build_overlays_from_context, finalize_world_state
from kernel.world_state import WorldStateV1


def make_minimal_context_for_chat(*, chat_id: str, user_id: str | None = None) -> TelegramContext:
    raw: Dict[str, Any] = {}
    if user_id is not None:
        raw = {"message": {"from": {"id": int(user_id)}, "chat": {"id": str(chat_id)}}}
    return TelegramContext(
        update_id=0,
        chat_id=str(chat_id),
        message_id=None,
        text="",
        command=None,
        args="",
        is_callback=False,
        callback_data=None,
        callback_query_id=None,
        raw=raw,
    )


def apply_telegram_overlays(
    ws: WorldStateV1,
    *,
    user_patch: Optional[Dict[str, Any]] = None,
    behavior_patch: Optional[Dict[str, Any]] = None,
    behavioral_state: Optional[Dict[str, Any]] = None,
    price_constraints: Optional[Dict[str, Any]] = None,
) -> WorldStateV1:
    u = dict(ws.user or {})
    if isinstance(user_patch, dict) and user_patch:
        u.update(user_patch)
    if isinstance(behavioral_state, dict) and behavioral_state:
        u["behavioral_state"] = behavioral_state

    beh = dict(ws.behavior or {})
    if isinstance(behavior_patch, dict) and behavior_patch:
        beh.update(behavior_patch)

    pc = ws.price_constraints
    if isinstance(price_constraints, dict):
        pc = dict(price_constraints)

    return WorldStateV1(
        schema_version=ws.schema_version,
        user=u,
        session=ws.session,
        product=ws.product,
        economy=ws.economy,
        timestamp_ms=ws.timestamp_ms,
        tenant_id=ws.tenant_id,
        meta=ws.meta,
        user_id=ws.user_id,
        safe_mode=ws.safe_mode,
        capital=ws.capital,
        horizon_state=ws.horizon_state,
        behavior=beh,
        price_constraints=pc,
        deployment_proposal=ws.deployment_proposal,
        manual_override=ws.manual_override,
    )


def build_system_world_state(
    *,
    purpose: str,
    session: Optional[Dict[str, Any]] = None,
    tenant_id: str | None = None,
    meta: Optional[Dict[str, Any]] = None,
    user_timezone: str = "Europe/Amsterdam",
    now_ms: Optional[int] = None,
) -> WorldStateV1:
    ts = int(now_ms if now_ms is not None else time.time() * 1000)
    return WorldStateV1(
        schema_version=1,
        user={"timezone": str(user_timezone or "Europe/Amsterdam")},
        session=dict(session or {}),
        product={"name": "BusinesAIOS Workspace"},
        economy={},
        timestamp_ms=ts,
        tenant_id=str(tenant_id) if tenant_id is not None else None,
        user_id="system",
        meta={"purpose": str(purpose or "system"), **(dict(meta or {}))},
    )


def latest_events(*, event_store: Any, tenant_id: str, user_id: str, limit: int = 800) -> List[Dict[str, Any]]:
    lim = max(1, min(5000, int(limit)))
    try:
        events = event_store.latest_events(tenant_id=str(tenant_id), user_id=str(user_id), limit=lim)
    except TypeError:
        events = event_store.latest_events(user_id=str(user_id), limit=lim)
    except Exception:
        events = []
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def build_world_state_for_telegram(
    *,
    event_store: Any,
    ctx: TelegramContext,
    tenant_id: str,
    user_timezone: str = "Europe/Amsterdam",
    economy: Optional[Dict[str, Any]] = None,
    entitlements: Optional[Dict[str, Any]] = None,
    product_context: Optional[Dict[str, Any]] = None,
    limit: int = 800,
    now_ms: Optional[int] = None,
) -> WorldStateV1:
    overlays = build_overlays_from_context(
        ctx=ctx,
        now_ms=now_ms,
        tenant_id=str(tenant_id or "default"),
        user_timezone=user_timezone,
        economy=economy,
        entitlements=entitlements,
        product_context=product_context,
    )
    events = latest_events(event_store=event_store, tenant_id=str(tenant_id or "default"), user_id=str(ctx.chat_id), limit=int(limit))
    ws = build_world_state_from_events(
        events,
        session=dict(overlays.session),
        meta=dict(overlays.meta),
        product=dict(overlays.product),
        economy=dict(overlays.economy),
        entitlements=dict(overlays.entitlements),
    )
    ws = apply_causal_overlay(ws=ws, events=events)
    return finalize_world_state(ws=ws, overlays=overlays)
