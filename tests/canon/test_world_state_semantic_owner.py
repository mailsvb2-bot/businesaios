from contracts.decisioning.decision_context_projection import DecisionContextProjection
from contracts.decisioning.world_state_contract import WorldStateContract
from core.economics.capital_allocation_engine import CapitalAllocationContext, WorldState
from kernel.world_state import WorldStateV1


def test_advisory_world_state_name_is_compatibility_only() -> None:
    assert WorldStateContract is DecisionContextProjection
    assert DecisionContextProjection.__module__ == "contracts.decisioning.decision_context_projection"
    assert DecisionContextProjection is not WorldStateV1


def test_capital_world_state_name_is_compatibility_only() -> None:
    assert WorldState is CapitalAllocationContext
    assert CapitalAllocationContext.__module__ == "core.economics.capital_allocation_engine"
