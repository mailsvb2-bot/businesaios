from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.allocation.allocation_constraints import AllocationConstraints
from core.finance.strategic.decimal_utils import q2


class CapitalAllocator:
    def allocate(
        self,
        available_capital: Decimal,
        entities: tuple[str, ...],
        constraints: AllocationConstraints,
    ) -> dict[str, Decimal]:
        if not entities:
            return {}
        spendable = max(Decimal('0'), available_capital - constraints.min_cash_buffer)
        per_entity_cap = q2(spendable * constraints.max_entity_share)
        remaining = spendable
        allocations: dict[str, Decimal] = {}
        for index, entity in enumerate(entities, start=1):
            slots_left = Decimal(str(len(entities) - index + 1))
            equal_share = q2(remaining / slots_left)
            allocation = min(per_entity_cap, equal_share)
            allocations[entity] = allocation
            remaining = q2(remaining - allocation)
        if remaining > Decimal('0'):
            first = entities[0]
            allocations[first] = q2(allocations[first] + remaining)
        return allocations
