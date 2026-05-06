from __future__ import annotations

from core.finance.strategic.adapters.economics_snapshot_adapter import EconomicsSnapshotToFinancialInputAdapter
from core.finance.strategic.input.financial_input_builder import FinancialInputBuilder


class StrategicFinanceInputBuilder(EconomicsSnapshotToFinancialInputAdapter):
    """Compatibility name bound to the canonical economics->finance adapter."""

    def __init__(self, builder: FinancialInputBuilder | None = None) -> None:
        super().__init__(builder=builder or FinancialInputBuilder())
