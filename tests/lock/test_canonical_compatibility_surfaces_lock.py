from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.planning.long_horizon_planner import (
    LongHorizonPlanner as CanonicalLongHorizonPlanner,
)
from application.planning.strategy_memory import (
    StrategyMemoryService as CanonicalStrategyMemoryService,
)
from core.ai import reset_decision_core_singleton, set_decision_core_singleton
from core.strategic_horizon import constants, engine
from execution.long_horizon_planner import LongHorizonPlanner
from execution.strategy_memory import StrategyMemoryService
from runtime import admin_state_support
from runtime import decision_gateway as canonical_decision_gateway
from runtime._internal.effects_domains import admin_pricing_effects
from runtime._internal.effects_domains import (
    admin_state_support as canonical_admin_state_support,
)
from runtime.decision_gateway import (
    DecisionGatewayContractError,
    RuntimeDecisionRouteGateway,
    optimize_runtime_decision,
    validate_runtime_decision_issuer,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    reset_decision_core_singleton()
    try:
        yield
    finally:
        reset_decision_core_singleton()


def test_planning_compatibility_surfaces_are_identity_aliases() -> None:
    assert LongHorizonPlanner is CanonicalLongHorizonPlanner
    assert StrategyMemoryService is CanonicalStrategyMemoryService


def test_strategic_engine_reexports_policy_owned_constants() -> None:
    for name in (
        "MAX_RISK_BUDGET",
        "MIN_MARGIN_SAFE",
        "MIN_RISK_BUDGET",
        "MIN_RUNWAY_DEFENSE",
        "MIN_RUNWAY_STABILIZE",
        "MODE_COOLDOWN_SECONDS",
    ):
        assert engine.__dict__[name] is constants.__dict__[name]


def test_admin_state_declared_exports_all_resolve() -> None:
    for name in admin_state_support.__all__:
        assert getattr(admin_state_support, name) is not None
        assert name in dir(admin_state_support)


def test_admin_pricing_effects_reuse_canonical_mutation_owners() -> None:
    assert (
        admin_pricing_effects.apply_pricing_change_effect
        is canonical_admin_state_support.apply_pricing_change_effect
    )
    assert (
        admin_pricing_effects.request_pricing_change_effect
        is canonical_admin_state_support.request_pricing_change_effect
    )
    assert (
        admin_pricing_effects.reject_pricing_change_effect
        is canonical_admin_state_support.reject_pricing_change_effect
    )


def test_platform_control_center_tests_have_unique_basenames() -> None:
    names = Counter(
        path.name for path in (ROOT / "tests").rglob("test_*.py")
    )
    assert names["test_platform_control_center_service.py"] == 1
    assert (
        names["test_platform_control_center_advisory_service.py"]
        == 1
    )


def test_gateway_rejects_an_unregistered_decision_issuer() -> None:
    class Issuer:
        def issue(self, state):
            return state

    registered = Issuer()
    set_decision_core_singleton(registered)
    validate_runtime_decision_issuer(registered)

    with pytest.raises(
        DecisionGatewayContractError,
        match="noncanonical_decision_issuer",
    ):
        validate_runtime_decision_issuer(Issuer())


def test_route_gateway_rejects_an_arbitrary_callable() -> None:
    gateway = RuntimeDecisionRouteGateway(
        decision_input_service=SimpleNamespace(),
        enrichment_service=SimpleNamespace(),
        observability=SimpleNamespace(),
    )
    packet = SimpleNamespace(
        recommendation_packet=SimpleNamespace(
            world_state=SimpleNamespace(generated_at_ms=0)
        )
    )

    with pytest.raises(
        DecisionGatewayContractError,
        match="noncanonical_decision_callable",
    ):
        gateway.route(
            packet=packet,
            canonical_context={},
            decision_core_callable=lambda state: state,
        )


def test_optimize_gateway_enforces_singleton_identity_and_exact_method() -> None:
    marker = object()

    class Optimizer:
        def issue(self, state):
            return state

        def optimize(self, state):
            assert state == "state"
            return marker

    optimizer = Optimizer()
    set_decision_core_singleton(optimizer)

    assert (
        optimize_runtime_decision(
            issuer=optimizer,
            state="state",
        )
        is marker
    )

    with pytest.raises(
        DecisionGatewayContractError,
        match="noncanonical",
    ):
        optimize_runtime_decision(
            issuer=optimizer,
            state="state",
            method_name="decide",
        )

    with pytest.raises(
        DecisionGatewayContractError,
        match="noncanonical_decision_issuer",
    ):
        optimize_runtime_decision(
            issuer=Optimizer(),
            state="state",
        )


def test_runtime_gateway_exposes_no_structured_alternate_issuer() -> None:
    assert not hasattr(
        canonical_decision_gateway,
        "issue_structured_decision",
    )
    assert (
        canonical_decision_gateway.CANON_RUNTIME_DECISION_GATEWAY_NO_STRUCTURED_ALT_ISSUER
        is True
    )
