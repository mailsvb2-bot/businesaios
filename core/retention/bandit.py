"""Thompson-sampling bandit for offer/price selection.

We store per-arm Beta(alpha,beta) in SQLite (via RetentionStore helpers).
Selection rule:
  choose arm with max( sample(theta_arm) * profit_if_success )

This is the minimal production form of "expected profit" while keeping
A/B exploration stable.
"""

from __future__ import annotations

import random
import time

from core.retention.ports import RetentionStore


def choose_arm(
    store: RetentionStore,
    *,
    tenant_id: str,
    arms: list[tuple[str, float]],
    now_ms: int | None = None,
) -> str:
    if not arms:
        return "NONE"
    now_ms = int(now_ms or int(time.time() * 1000))

    best_arm = arms[0][0]
    best_score = -1.0

    for arm, profit in arms:
        store.bandit_ensure_arm(tenant_id=tenant_id, arm=arm, now_ms=now_ms)
        a, b = store.bandit_get_arm(tenant_id=tenant_id, arm=arm)
        theta = random.betavariate(float(a), float(b))
        score = float(theta) * float(profit)
        if score > best_score:
            best_score = score
            best_arm = arm

    return best_arm


def update_arm(
    store: RetentionStore,
    *,
    tenant_id: str,
    arm: str,
    success: bool,
    now_ms: int | None = None,
) -> None:
    if not arm or arm == "NONE":
        return
    now_ms = int(now_ms or int(time.time() * 1000))
    store.bandit_update_arm(tenant_id=tenant_id, arm=arm, success=bool(success), now_ms=now_ms)
