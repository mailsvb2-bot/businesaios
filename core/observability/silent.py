"""Non-silent exception swallowing helpers.

Rule:
- Best-effort paths may *swallow* exceptions, but never silently.
- Use swallow() only when the caller has a valid fallback behavior.

This module keeps observability bounded (throttled) and dependency-free.
"""

from __future__ import annotations

import logging
from typing import Any

from core.observability.throttled_logger import exception_throttled


def swallow(module: str, where: str, *, throttle_ms: int = 30_000, extra: dict[str, Any] | None = None) -> None:
    """Log a swallowed exception (throttled).

    Must be called from inside an except block.

    Args:
        module: usually __name__
        where: short location label (e.g. "telegram.outbound.enqueue")
    """

    lg = logging.getLogger(str(module) if module else "swallow")
    key = f"swallow:{module}:{where}"
    msg = f"swallowed exception: {where}"
    exception_throttled(lg, key=key, msg=msg, throttle_ms=throttle_ms, extra=extra)
