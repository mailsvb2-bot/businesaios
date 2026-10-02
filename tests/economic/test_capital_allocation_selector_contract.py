from __future__ import annotations

from core.economics.capital_allocation_engine import CapitalAllocationEngine
from core.economics.contracts import EconomicsContext


class _CanonicalSelector:
    def __init__(self) -> None:
        self.context: EconomicsContext | None = None

    def build_recommendations(self, context: EconomicsContext):
        self.context = context
        return [
            {
                "candidate": "retention",
                "expected_value": 1.0,
                "estimated_cost": 0.2,
            }
        ]


def test_capital_allocation_engine_calls_declared_selector_contract() -> None:
    selector = _CanonicalSelector()
    engine = CapitalAllocationEngine(selector=selector)

    recommendations = engine.score_options(
        tenant_id="tenant-a",
        correlation_id="corr-a",
        payload={"budget": 100.0},
    )

    assert recommendations == [
        {
            "candidate": "retention",
            "expected_value": 1.0,
            "estimated_cost": 0.2,
        }
    ]
    assert selector.context == EconomicsContext(
        tenant_id="tenant-a",
        correlation_id="corr-a",
        payload={"budget": 100.0},
    )
