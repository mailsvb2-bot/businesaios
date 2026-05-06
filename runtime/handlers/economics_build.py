from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.economics import BudgetEnvelope, UnitEconomicsSnapshot, build_budget_envelope


def handle_economics_build(snapshot: UnitEconomicsSnapshot) -> BudgetEnvelope:
    return build_budget_envelope(snapshot)
