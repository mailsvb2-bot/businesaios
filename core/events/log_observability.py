from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def commit_store_if_supported(store: Any) -> None:
    if not hasattr(store, "commit"):
        return
    store.commit()


def log_commit_failure() -> None:
    try:
        log.exception("event_log: commit failed")
    except Exception:
        return


def build_system_error_payload(*, event_type: str, details: dict) -> dict[str, Any]:
    return {"event_type": str(event_type), "details": dict(details or {})}
