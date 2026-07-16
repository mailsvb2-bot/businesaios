from __future__ import annotations

import ast
from pathlib import Path

from canon.anti_second_brain_rules import DECISION_AUTHORITY_METHODS
from tools.architecture_bypass_scanner import (
    DECISION_BYPASS_CALLS,
    _scan_ast,
)


def _scan_source(*, tmp_path: Path, relative: str, source: str):
    root = tmp_path / "repo"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    return _scan_ast(root=root, path=path, rel=relative, tree=tree)


def test_decision_bypass_vocabulary_is_bound_to_canon() -> None:
    assert DECISION_BYPASS_CALLS is DECISION_AUTHORITY_METHODS


def test_nested_self_decision_call_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/service.py",
        source=(
            "class FeatureService:\n"
            "    def run(self, state):\n"
            "        return self.shadow_brain.decide(state)\n"
        ),
    )

    assert [item.code for item in findings] == ["possible_decision_core_bypass"]
    assert "self.shadow_brain.decide" in findings[0].detail


def test_chained_registry_decision_call_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="runtime/feature_bridge.py",
        source=(
            "def run(registry, state):\n"
            "    return registry.get('decision').issue(state)\n"
        ),
    )

    assert [item.code for item in findings] == ["possible_decision_core_bypass"]
    assert "registry.get().issue" in findings[0].detail


def test_direct_decision_function_call_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/direct.py",
        source=(
            "from hidden import decide\n"
            "def run(state):\n"
            "    return decide(state)\n"
        ),
    )

    assert [item.code for item in findings] == ["possible_decision_core_bypass"]


def test_contextual_local_optimizer_does_not_become_false_second_brain(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/pricing/calculator.py",
        source=(
            "class PricingCalculator:\n"
            "    def calculate(self, state):\n"
            "        return self.optimizer.optimize(state)\n"
        ),
    )

    assert findings == []


def test_contextual_shadow_planner_optimizer_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/planner.py",
        source=(
            "class FeaturePlanner:\n"
            "    def run(self, state):\n"
            "        return self.shadow_planner.optimize(state)\n"
        ),
    )

    assert [item.code for item in findings] == ["possible_decision_core_bypass"]


def test_canonical_decision_owner_path_remains_allowed(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/decision_runtime/runner.py",
        source=(
            "def run(decision_core, state):\n"
            "    return decision_core.decide(state)\n"
        ),
    )

    assert findings == []
