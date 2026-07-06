"""Canonical error logging helpers.

This module exists to avoid "second lines" of observability.

Historically, different subsystems used different helpers for throttled
exception logging. The canonical implementation lives in
`core.observability.throttled_logger.exception_throttled`.

This file provides a stable import path (`core.observability.errors`) that
other modules can depend on without re-implementing throttling.
"""

from __future__ import annotations

from typing import Any

from core.observability.throttled_logger import exception_throttled


def log_exception_throttled(
    logger: Any,
    *,
    key: str,
    msg: str,
    throttle_ms: int = 10_000,
) -> None:
    """Log an exception in a throttled way.

    This helper intentionally does not accept the exception object. It is meant
    to be used inside an `except Exception:` block where the active exception
    is available implicitly.
    """

    try:
        exception_throttled(logger, key=str(key), msg=str(msg), throttle_ms=int(throttle_ms))
    except Exception:
        # Observability must never crash runtime.
        return
