from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.business_roi_registry import BusinessROIRegistry
from execution.capital_allocation_policy import CapitalAllocationPolicy

CANON_PORTFOLIO_ALLOCATOR = True


@dataclass(frozen=True, slots=True)
class PortfolioAllocationPlan:
    allocations: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"allocations": list(self.allocations), "metadata": dict(self.metadata)}


class PortfolioAllocator:
    def __init__(self) -> None:
        self._registry = BusinessROIRegistry()
        self._policy = CapitalAllocationPolicy()

    def plan(self, *, portfolio_signals: Mapping[str, Mapping[str, Any]] | None) -> PortfolioAllocationPlan:
        signals = self._registry.normalize(entries=portfolio_signals)
        allocations = tuple(item.to_dict() for item in self._policy.allocate(signals=signals))
        return PortfolioAllocationPlan(allocations=allocations, metadata={"owner": "execution.portfolio_allocator"})


__all__ = ["CANON_PORTFOLIO_ALLOCATOR", "PortfolioAllocator", "PortfolioAllocationPlan"]
