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
from core.strategic_horizon import constants, engine
from execution.long_horizon_planner import LongHorizonPlanner
from execution.strategy_memory import StrategyMemoryService
from runtime import admin_state_support
from runtime.decision_gateway import (
    DecisionGatewayContractError,
    issue_structured_decision,
    optimize_runtime_decision,
)

ROOT = Path(__file__).resolve().parents[2]


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


def test_platform_control_center_tests_have_unique_basenames() -> None:
    names = Counter(
        path.name for path in (ROOT / "tests").rglob("test_*.py")
    )
    assert names["test_platform_control_center_service.py"] == 1
    assert (
        names["test_platform_control_center_advisory_service.py"]
        == 1
    )


def test_optimize_gateway_enforces_exact_method() -> None:
    marker = object()

    class Optimizer:
        def optimize(self, state):
            assert state == "state"
            return marker

    assert (
        optimize_runtime_decision(
            issuer=Optimizer(),
            state="state",
        )
        is marker
    )

    with pytest.raises(
        DecisionGatewayContractError,
        match="noncanonical",
    ):
        optimize_runtime_decision(
            issuer=Optimizer(),
            state="state",
            method_name="decide",
        )


def test_structured_gateway_preserves_argument_contract() -> None:
    captured = SimpleNamespace(args=None)

    class Issuer:
        def issue(self, space, constraints, request):
            captured.args = (space, constraints, request)
            return "result"

    assert (
        issue_structured_decision(
            issuer=Issuer(),
            decision_space="space",
            constraints="constraints",
            request="request",
        )
        == "result"
    )
    assert captured.args == ("space", "constraints", "request")
