from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def safe_setattr(obj: Any, name: str, value: Any) -> bool:
    try:
        setattr(obj, name, value)
        return True
    except (AttributeError, TypeError) as exc:
        logger.warning("safe_setattr_failed", extra={"attr": name, "owner": type(obj).__name__}, exc_info=exc)
        return False
