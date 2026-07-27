"""Retention bandit state compatibility helpers.

Historical arm selection lived here. Final selection now belongs exclusively to
DecisionCore; this module only records outcomes and rejects autonomous choice.
"""

from __future__ import annotations

import time

from core.retention.ports import RetentionStore


def choose_arm(
    store: RetentionStore,
    *,
    tenant_id: str,
    arms: list[tuple[str, float]],
    now_ms: int | None = None,
) -> str:
    """Compatibility lock preventing retention from choosing outside DecisionCore."""

    del store, tenant_id, now_ms
    if not arms:
        return "NONE"
    raise RuntimeError("retention_arm_selection_requires_decision_core")


def update_arm(
    store: RetentionStore,
    *,
    tenant_id: str,
    arm: str,
    success: bool,
    now_ms: int | None = None,
) -> None:
    """Record an observed outcome; learning remains allowed after execution."""

    if not arm or arm == "NONE":
        return
    observed_at_ms = int(now_ms or int(time.time() * 1000))
    store.bandit_update_arm(
        tenant_id=tenant_id,
        arm=arm,
        success=bool(success),
        now_ms=observed_at_ms,
    )
