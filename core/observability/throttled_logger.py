"""Throttled logging helpers.

Purpose:
- Replace silent 'pass' in exception handlers with bounded observability.
- Keep system best-effort (do not crash), but never hide failures silently.

This module is intentionally tiny and dependency-free.
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


def _should_emit(key: str, throttle_ms: int) -> bool:
    """Check and update throttle state atomically."""
    now = _now_ms()
    with _LOCK:
        prev = _LAST_MS.get(str(key), 0)
        if (now - prev) < int(throttle_ms):
            return False
        _LAST_MS[str(key)] = now
        return True


def exception_throttled(
    logger: logging.Logger,
    *,
    key: str,
    msg: str,
    throttle_ms: int = 30_000,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log an exception at most once per throttle window.

    Must be called from inside an except block (uses logger.exception()).
    Never raises.
    """
    try:
        if not _should_emit(key, throttle_ms):
            return
        if extra:
            logger.exception(msg, extra={"throttle_key": str(key), **dict(extra)})
        else:
            logger.exception(msg)
    except Exception:
        return


def warning_throttled(
    logger: logging.Logger,
    *,
    key: str,
    msg: str,
    throttle_ms: int = 30_000,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log a warning at most once per throttle window."""
    try:
        if not _should_emit(key, throttle_ms):
            return
        if extra:
            logger.warning(msg, extra={"throttle_key": str(key), **dict(extra)})
        else:
            logger.warning(msg)
    except Exception:
        return
