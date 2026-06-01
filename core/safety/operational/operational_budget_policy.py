from __future__ import annotations

from dataclasses import dataclass

CANON_OPERATIONAL_BUDGET_POLICY = True


@dataclass(frozen=True)
class OperationalBudgetPolicy:
    max_actions_per_hour: int = 25
    max_actions_per_day: int = 150
    max_budget_minor_per_day: int = 250_000
    max_new_publications_per_day: int = 8
    max_outbound_messages_per_day: int = 80
    max_strategic_changes_without_human_approval_per_day: int = 0
    max_rollback_triggers_per_day: int = 3

    def validate(self) -> None:
        values = {
            "max_actions_per_hour": self.max_actions_per_hour,
            "max_actions_per_day": self.max_actions_per_day,
            "max_budget_minor_per_day": self.max_budget_minor_per_day,
            "max_new_publications_per_day": self.max_new_publications_per_day,
            "max_outbound_messages_per_day": self.max_outbound_messages_per_day,
            "max_strategic_changes_without_human_approval_per_day": (
                self.max_strategic_changes_without_human_approval_per_day
            ),
            "max_rollback_triggers_per_day": self.max_rollback_triggers_per_day,
        }
        for name, value in values.items():
            if int(value) < 0:
                raise ValueError(f"{name} must be >= 0")


__all__ = [
    "OperationalBudgetPolicy",
]