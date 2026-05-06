"""Payment effect helpers.

Extracted from payments_actions.py (Patch 06).
Each function is a small, testable primitive.
"""

from __future__ import annotations
from typing import Any, Dict, Optional


def validate_payment_amount(amount: Any, *, currency: str = "RUB") -> float:
    """Validate and normalize payment amount.

    Returns amount as float. Raises ValueError on invalid input.
    """
    try:
        val = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid payment amount: {amount!r}")
    if val < 0:
        raise ValueError(f"Negative payment amount: {val}")
    if val > 1_000_000:
        raise ValueError(f"Payment amount exceeds limit: {val}")
    return round(val, 2)


def build_access_grant_payload(
    *,
    user_id: str,
    product_id: str,
    duration_days: int,
    payment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a deterministic access grant payload."""
    return {
        "user_id": str(user_id),
        "product_id": str(product_id),
        "duration_days": int(duration_days),
        "payment_id": str(payment_id) if payment_id else None,
    }


def reconcile_payment_status(
    *,
    provider_status: str,
    local_status: str,
) -> str:
    """Determine canonical payment status from provider + local.

    Returns: 'succeeded' | 'pending' | 'failed' | 'refunded' | 'conflict'
    """
    TERMINAL = {"succeeded", "failed", "refunded", "canceled"}
    ps = str(provider_status).lower().strip()
    ls = str(local_status).lower().strip()

    if ps == ls:
        return ps
    if ps in TERMINAL and ls not in TERMINAL:
        return ps
    if ls in TERMINAL and ps not in TERMINAL:
        return ls
    # Both terminal but disagree — conflict
    return "conflict"
