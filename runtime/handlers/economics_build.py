from __future__ import annotations

from runtime.economics import BudgetEnvelope, UnitEconomicsSnapshot, build_budget_envelope

CANON_THIN_HANDLER = True

def handle_economics_build(snapshot: UnitEconomicsSnapshot) -> BudgetEnvelope:
    return build_budget_envelope(snapshot)
