from __future__ import annotations

import logging

from runtime.observability.error_handling import warning_throttled


def throttled_exec_warn(logger: logging.Logger, key: str, e: Exception) -> None:
    warning_throttled(
        logger,
        key=f"runtime_executor:{key}",
        msg=f"runtime_executor_warn key={key} err={e.__class__.__name__}",
        throttle_ms=10_000,
    )
