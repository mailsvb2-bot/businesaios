from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from core.events.event_types import normalize_event_type


def reduce_event(state: dict[str, Any], ev: Mapping[str, Any]) -> dict[str, Any]:
    """Pure reducer: (state, event) -> new_state.

    The reducer is deliberately minimal and bounded.
    Its output is used to build stable user/session slices of WorldState.
    """

    et = normalize_event_type(str(ev.get("event_type") or ""))
    payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}

    s = dict(state)
    try:
        s["last_ts_ms"] = max(int(s.get("last_ts_ms") or 0), int(ev.get("timestamp_ms") or 0))
    except Exception:
        s["last_ts_ms"] = int(s.get("last_ts_ms") or 0)

    if et == "session_start":
        s["sessions_7d"] = int(s.get("sessions_7d") or 0) + 1
    elif et == "purchase_success":
        s["purchases_30d"] = int(s.get("purchases_30d") or 0) + 1
        s["last_purchase_offer_id"] = str(payload.get("offer_id") or "")
    elif et == "audio_progress":
        try:
            s["listen_seconds_7d"] = int(s.get("listen_seconds_7d") or 0) + int(payload.get("delta_s") or 0)
        except Exception:
            s["listen_seconds_7d"] = int(s.get("listen_seconds_7d") or 0)
    elif et == "offer_clicked":
        s["offer_clicks_7d"] = int(s.get("offer_clicks_7d") or 0) + 1
    elif et == "mood_logged":
        s["mood_last"] = payload.get("mood")

    return s
