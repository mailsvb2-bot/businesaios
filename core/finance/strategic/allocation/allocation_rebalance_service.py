from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class AllocationRebalanceService:
    def rebalance(
        self,
        current: dict[str, Decimal],
        target: dict[str, Decimal],
        tolerance: Decimal = Decimal('0.05'),
    ) -> dict[str, Decimal]:
        changes: dict[str, Decimal] = {}
        for key, target_value in target.items():
            current_value = current.get(key, Decimal('0'))
            delta = q2(target_value - current_value)
            baseline = max(abs(target_value), Decimal('0.01'))
            if abs(delta) / baseline >= tolerance:
                changes[key] = delta
        return changes
