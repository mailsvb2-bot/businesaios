"""Shared runtime-only helpers for sealed effects state.

This module keeps the private effects implementation focused on composition
instead of accumulating every helper and mutable field concern.
"""

from __future__ import annotations

import time
from typing import Any


def initialize_effects_runtime_state(effects: Any) -> None:
    if effects._last_sent is None:
        effects._last_sent = {}
    if effects._telegram_me is None:
        effects._telegram_me = None
    effects._telegram_webhook_cleared = bool(effects._telegram_webhook_cleared)
    effects._telegram_startup_checked = bool(getattr(effects, "_telegram_startup_checked", False))
    if effects._last_err_ms is None:
        effects._last_err_ms = {}


def throttled_emit_error(
    *,
    event_log: Any,
    cache: dict[str, int] | None,
    key: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    try:
        now_ms = int(time.time() * 1000)
        last = int((cache or {}).get(key, 0))
        if (now_ms - last) < 10_000:
            return
        if cache is not None:
            cache[key] = now_ms
        if event_log is None:
            return
        event_log.emit(
            event_type=str(event_type),
            source="runtime.effects.telegram",
            user_id="system",
            decision_id="system",
            correlation_id="system",
            payload=dict(payload),
        )
    except Exception:
        return


__all__ = [
    "initialize_effects_runtime_state",
    "throttled_emit_error",
]
