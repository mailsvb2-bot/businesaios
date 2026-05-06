from __future__ import annotations

from dataclasses import dataclass

from config.market_balance_limits import MAX_CONCENTRATION_RATIO, OVERFLOW_WARN_RATIO, UTILIZATION_WARN_RATIO

CANON_MARKET_BALANCE_ALIAS_NAMESPACE = True

class CapacityOverflowGuard:
    def detect(self, overflow_ratio: float) -> bool:
        return float(overflow_ratio) >= OVERFLOW_WARN_RATIO

class DemandDistributionMonitor:
    def concentration_ratio(self, routed_counts: dict[str, int]) -> float:
        total = sum(routed_counts.values()) or 1
        return max(routed_counts.values(), default=0) / total

@dataclass(frozen=True, slots=True)
class MarketHealthSnapshot:
    utilization_ratio: float
    concentration_ratio: float
    overflow_ratio: float
    alerts: tuple[str, ...]

class NewSupplySupportEngine:
    def bonus(self, tags: tuple[str, ...]) -> float:
        return 0.1 if "new_supply" in tags else 0.0

class OverconcentrationDetector:
    def detect(self, concentration_ratio: float) -> bool:
        return float(concentration_ratio) > MAX_CONCENTRATION_RATIO

class SaturationDetector:
    def detect(self, utilization_ratio: float) -> bool:
        return float(utilization_ratio) >= UTILIZATION_WARN_RATIO

class SupplyUtilizationMonitor:
    def utilization_ratio(self, live_states: tuple[object, ...]) -> float:
        if not live_states:
            return 0.0
        return sum(1.0 - float(s.capacity_score) for s in live_states) / len(live_states)

class UnfairRoutingDetector:
    def detect(self, concentration_ratio: float, utilization_ratio: float) -> bool:
        return concentration_ratio > 0.5 and utilization_ratio < 0.5

__all__ = [
    "CapacityOverflowGuard",
    "DemandDistributionMonitor",
    "MarketHealthSnapshot",
    "NewSupplySupportEngine",
    "OverconcentrationDetector",
    "SaturationDetector",
    "SupplyUtilizationMonitor",
    "UnfairRoutingDetector",
]
