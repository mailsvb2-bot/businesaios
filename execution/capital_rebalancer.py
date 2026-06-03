from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.portfolio_allocator import PortfolioAllocator

CANON_CAPITAL_REBALANCER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True, slots=True)
class CapitalRebalancePlan:
    deltas: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"deltas": list(self.deltas), "metadata": dict(self.metadata)}


class CapitalRebalancer:
    def __init__(self) -> None:
        self._allocator = PortfolioAllocator()

    def build_plan(self, *, portfolio_signals: Mapping[str, Mapping[str, Any]] | None, current_allocations: Mapping[str, Any] | None) -> CapitalRebalancePlan:
        target = self._allocator.plan(portfolio_signals=portfolio_signals)
        current = _safe_dict(current_allocations)
        deltas = []
        for entry in target.allocations:
            key = str(entry.get("business_key") or "")
            deltas.append({
                "business_key": key,
                "target_share": float(entry.get("target_share") or 0.0),
                "current_share": _safe_float(current.get(key)),
                "delta": float(entry.get("target_share") or 0.0) - _safe_float(current.get(key)),
            })
        return CapitalRebalancePlan(deltas=tuple(deltas), metadata={"owner": "execution.capital_rebalancer"})


__all__ = ["CANON_CAPITAL_REBALANCER", "CapitalRebalancer", "CapitalRebalancePlan"]
