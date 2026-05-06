from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class BudgetAllocator:
    def allocate(self, total_budget: Decimal, buckets: tuple[str, ...]) -> dict[str, Decimal]:
        if not buckets:
            return {}
        allocations: dict[str, Decimal] = {}
        remaining = total_budget
        for index, bucket in enumerate(buckets, start=1):
            slots_left = Decimal(str(len(buckets) - index + 1))
            share = q2(remaining / slots_left)
            allocations[bucket] = share
            remaining = q2(remaining - share)
        if remaining != Decimal('0'):
            allocations[buckets[0]] = q2(allocations[buckets[0]] + remaining)
        return allocations
