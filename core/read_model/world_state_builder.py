from __future__ import annotations

import time
from typing import Any, Dict

from kernel.world_state import WorldStateV1
from core.read_model.reducers import reduce_event


def build_world_state_from_events(
    *,
    tenant_id: str,
    user_id: str,
    session: Dict[str, Any],
    product: Dict[str, Any],
    economy: Dict[str, Any],
    events: list[dict],
) -> WorldStateV1:
    """Deterministic builder: events -> reduced snapshot -> WorldStateV1.

    This builder does NOT perform I/O. It only reduces events passed in.
    """

    base: Dict[str, Any] = {
        "last_ts_ms": 0,
        "sessions_7d": 0,
        "purchases_30d": 0,
        "listen_seconds_7d": 0,
        "offer_clicks_7d": 0,
    }

    st = dict(base)
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        st = reduce_event(st, ev)

    user = {"id": str(user_id), **st}
    return WorldStateV1(
        schema_version=1,
        user=user,
        session=dict(session or {}),
        product=dict(product or {}),
        economy=dict(economy or {}),
        timestamp_ms=int(time.time() * 1000),
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        meta={},
    )
