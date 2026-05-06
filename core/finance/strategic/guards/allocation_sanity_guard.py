from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class AllocationSanityGuard:
    def check(self, allocation: dict[str, Decimal], total_budget: Decimal) -> GuardResult:
        if any(amount < 0 for amount in allocation.values()):
            return GuardResult(False, "allocation_negative", "allocation contains negative amounts")
        allocated = sum(allocation.values(), start=Decimal("0"))
        if allocated != total_budget:
            return GuardResult(False, "allocation_mismatch", "allocation total does not match budget", {"allocated": str(allocated), "budget": str(total_budget)})
        return GuardResult(True, "allocation_ok", "allocation is sane")
