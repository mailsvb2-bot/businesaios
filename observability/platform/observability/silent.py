"""Non-silent exception swallowing for platform observability compatibility paths.

Compatibility paths are allowed to be best-effort, but must never hide failures silently.
This module intentionally does NOT depend on core.* to preserve layering.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_LAST_MS: dict[str, int] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def swallow(module: str, where: str, *, throttle_ms: int = 30_000, extra: dict[str, Any] | None = None) -> None:
    """Log a swallowed exception (throttled). Must be called from inside except."""

    try:
        key = f"swallow:{module}:{where}"
        now = _now_ms()
        with _LOCK:
            prev = _LAST_MS.get(key, 0)
            if (now - prev) < int(throttle_ms):
                return
            _LAST_MS[key] = now
        lg = logging.getLogger(str(module) if module else "platform.compat.swallow")
        if extra:
            lg.exception(f"swallowed exception: {where}", extra={"swallow_where": where, **dict(extra)})
        else:
            lg.exception(f"swallowed exception: {where}")
    except Exception:
        return
