from __future__ import annotations

import logging
from typing import Any


def log_fallback(logger: logging.Logger, *, event: str, error: Exception, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.warning("fallback:%s", payload, exc_info=error)
