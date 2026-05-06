from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot


@dataclass
class BudgetHealthProjection:
    def project(self, snapshot: EconomicsSnapshot) -> dict:
        budget = snapshot.budget_envelope
        evaluation = snapshot.evaluation
        return {
            "snapshot_id": snapshot.snapshot_id.value,
            "available_growth_budget": budget.available_growth_budget,
            "protected_cash_reserve": budget.protected_cash_reserve,
            "recommended_spend_cap": budget.recommended_spend_cap,
            "pressure_level": budget.pressure_level.value,
            "budget_pressure_status": evaluation.budget_pressure_status.value,
            "guard_count": len(snapshot.guard_triggers),
            "blocking_guard": snapshot.has_blocking_guard,
        }
