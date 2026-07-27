from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action
from core.retention.decision_debug import build_retention_debug


def _debug(source: Any) -> dict[str, Any]:
    if source is None:
        return {}
    raw = getattr(source, "debug", None)
    if isinstance(raw, dict):
        return build_retention_debug(source)
    return {}


def apply_retention_constraints_to_state(
    *,
    state: Any,
    evaluation: Any = None,
    plan: Any = None,
) -> Any:
    """Apply deterministic evidence-derived constraints before base proposal."""

    debug = _debug(evaluation if evaluation is not None else plan)
    override = debug.get("price_constraints_override")
    if not isinstance(override, dict) or not override:
        return state
    existing = (
        state.price_constraints
        if isinstance(getattr(state, "price_constraints", None), dict)
        else {}
    )
    merged = dict(existing or {})
    merged.update({str(key): value for key, value in override.items() if str(key)})
    return replace(state, price_constraints=merged)


def merge_retention_plan(*, base: Any, plan: Any, user_id: str) -> ProposedAction:
    """Legacy compatibility without arbitrary nested execution plans.

    The live policy uses candidate proposals. Historical callers receive their
    original single action; telemetry/offer steps are not smuggled into an
    ``execute_plan@v1`` action that the canonical runtime cannot execute.
    """

    del plan, user_id
    return normalize_proposed_action(base)
