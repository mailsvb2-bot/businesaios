from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class SensitivitySimulator:
    def run(self, base_value: Decimal, deltas: tuple[Decimal, ...]) -> list[Decimal]:
        return [q2(base_value * (Decimal('1') + delta)) for delta in deltas]
