from __future__ import annotations

"""Ads apply limits (small, dumb primitives)."""

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class AdsApplyLimits:
    max_daily_budget_minor: int = 0
    max_changes_per_day: int = 0


def planned_stats(plan: Any) -> Tuple[int, int]:
    """Return (planned_daily_budget_minor, planned_changes). Best-effort."""
    cmds = getattr(plan, "commands", None)
    if not isinstance(cmds, list):
        return (0, 0)
    changes = len(cmds)
    budget_minor = 0
    for c in cmds:
        payload = getattr(c, "payload", {}) or {}
        # convention: payload may include daily_budget_minor
        v = payload.get("daily_budget_minor")
        if v is not None:
            try:
                budget_minor = max(budget_minor, int(v))
            except (TypeError, ValueError):
                continue
    return (int(budget_minor), int(changes))
