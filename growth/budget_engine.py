from __future__ import annotations

from growth.engine_base import GrowthEngineSurface
from growth.engine_contract import BUDGET_ENGINE_PACKAGE_KIND, build_package


class BudgetEngine(GrowthEngineSurface):

    def allocate_budget(self, payload: dict | None) -> dict:
        return self.artifact("budget_allocation", payload)

    def select_bid_strategy(self, payload: dict | None) -> dict:
        return self.artifact("bid_strategy", payload)

    def assemble_budget(self, payload: dict | None) -> dict:
        normalized = self.payload(payload)
        return build_package(
            BUDGET_ENGINE_PACKAGE_KIND,
            normalized,
            budget_allocation=self.allocate_budget(normalized),
            bid_strategy=self.select_bid_strategy(normalized),
        )


class BidStrategySelector:
    def __init__(self, *, engine: BudgetEngine | None = None) -> None:
        self._engine = engine or BudgetEngine()

    def select(self, payload: dict) -> dict:
        return self._engine.select_bid_strategy(payload)


class BudgetAllocator:
    def __init__(self, *, engine: BudgetEngine | None = None) -> None:
        self._engine = engine or BudgetEngine()

    def allocate(self, payload: dict) -> dict:
        return self._engine.allocate_budget(payload)


__all__ = ["BidStrategySelector", "BudgetAllocator", "BudgetEngine"]
