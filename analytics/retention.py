from __future__ import annotations

"""Retention / churn analytics (offline).

This module is pure: it works on a list/iterator of event dicts.
"""

from collections import defaultdict
from typing import Iterable, Dict, Any, Tuple
import time


def compute_retention(events: Iterable[Dict[str, Any]], *, window_days: int = 30, return_days: int = 7) -> float:
    """Compute simple retention ratio: returning / active within a window.

    - active_users: users with any event in last `window_days`
    - returning: users active both in [window_days] and in last `return_days`
    """
    now_ms = int(time.time() * 1000)
    window_ms = int(window_days) * 24 * 3600 * 1000
    return_ms = int(return_days) * 24 * 3600 * 1000

    active = set()
    recent = set()

    for ev in events:
        try:
            uid = str(ev.get("user_id"))
            ts = int(ev.get("timestamp_ms") or 0)
        except Exception:
            continue
        if not uid:
            continue
        if now_ms - ts <= window_ms:
            active.add(uid)
        if now_ms - ts <= return_ms:
            recent.add(uid)

    if not active:
        return 0.0
    returning = active & recent
    return float(len(returning)) / float(len(active))


def compute_churn(events: Iterable[Dict[str, Any]], *, window_days: int = 30, return_days: int = 7) -> float:
    r = compute_retention(events, window_days=window_days, return_days=return_days)
    return max(0.0, 1.0 - float(r))
