from __future__ import annotations

from typing import Any, Dict, Optional

from kernel.world_state import WorldStateV1


def build_world_state_for_chat(*, event_store: Any, tenant_id: str, chat_id: str, session: Optional[Dict[str, Any]] = None, meta: Optional[Dict[str, Any]] = None, product: Optional[Dict[str, Any]] = None, economy: Optional[Dict[str, Any]] = None, entitlements: Optional[Dict[str, Any]] = None, limit: int = 800) -> WorldStateV1:
    try:
        events = event_store.latest_events(
            tenant_id=tenant_id,
            user_id=str(chat_id),
            limit=int(limit),
        )
    except TypeError:
        events = event_store.latest_events(user_id=str(chat_id), limit=int(limit))

    if not isinstance(events, list):
        events = []

    from core.read_model.world_state_builder import build_world_state_from_events

    return build_world_state_from_events(
        events,
        session=(session or {}),
        meta=(meta or {}),
        product=(product or {}),
        economy=(economy or {}),
        entitlements=(entitlements or {}),
    )
