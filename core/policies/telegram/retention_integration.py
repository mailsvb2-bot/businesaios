from __future__ import annotations

from dataclasses import replace
from typing import Any


def apply_retention_constraints_to_state(*, state: Any, plan: Any) -> Any:
    if plan is None or not isinstance(getattr(plan, "debug", None), dict):
        return state
    override = plan.debug.get("price_constraints_override")
    if not isinstance(override, dict) or not override:
        return state
    existing = state.price_constraints if isinstance(getattr(state, "price_constraints", None), dict) else {}
    merged = dict(existing or {})
    merged.update({str(k): v for k, v in override.items() if str(k)})
    return replace(state, price_constraints=merged)


def merge_retention_plan(*, base: Any, plan: Any, user_id: str) -> Any:
    if plan is None or not getattr(plan, "steps", None):
        return base
    if isinstance(base, dict) and str(base.get("action")) == "execute_plan@v1":
        out = dict(base)
        out["steps"] = [*(list(base.get("steps") or [])), *plan.steps]
        return out
    return {"action": "execute_plan@v1", "user_id": str(user_id), "steps": [base, *plan.steps]}
