from __future__ import annotations

from decimal import Decimal


class AllocationExplainer:
    def explain(self, allocation: dict[str, Decimal], rationale: tuple[str, ...] = ()) -> str:
        ordered = ', '.join(f'{key}={value}' for key, value in sorted(allocation.items()))
        reasons = f" Rationale: {'; '.join(rationale)}." if rationale else ""
        return f'Allocation recommendation: {ordered}.{reasons}'
