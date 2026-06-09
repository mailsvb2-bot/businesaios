"""Executor dispatch helpers.

Extracted from RuntimeExecutor._dispatch (Patch 06).
"""

from __future__ import annotations

from typing import Any


def extract_user_id_from_payload(payload: Any) -> str:
    """Safely extract user_id from a decision payload."""
    if isinstance(payload, dict):
        return str(payload.get("user_id", "unknown"))
    return "unknown"


def should_skip_duplicate_delivery(
    *,
    outbox: Any,
    decision_id: str,
) -> bool:
    """Check if another worker already claimed this decision.

    Returns True if delivery should be skipped.
    """
    if outbox is None:
        return False
    if not hasattr(outbox, "claim"):
        return False
    return not outbox.claim(decision_id)
