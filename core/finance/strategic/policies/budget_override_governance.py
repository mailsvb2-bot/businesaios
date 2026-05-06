from __future__ import annotations


class BudgetOverrideGovernance:
    def can_override(self, actor_role: str, reason: str) -> bool:
        return actor_role in {'cfo', 'ceo'} and bool(reason.strip())
