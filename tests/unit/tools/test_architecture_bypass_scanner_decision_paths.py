from __future__ import annotations

import ast
from pathlib import Path

from canon.anti_second_brain_rules import DECISION_AUTHORITY_METHODS
from tools.architecture_bypass_scanner import (
    DECISION_BYPASS_CALLS,
    SCAN_ROOTS,
    _scan_ast,
    scan,
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


def test_source_discovery_is_not_bound_to_a_root_allowlist() -> None:
    assert SCAN_ROOTS == ()


def test_repository_wide_scan_covers_new_product_roots_and_prunes_builds(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "new_product_root" / "service.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "def run(shadow_brain, state):\n"
        "    return shadow_brain.decide(state)\n",
        encoding="utf-8",
    )
    generated = root / "target" / "generated.py"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(
        "def run(shadow_brain, state):\n"
        "    return shadow_brain.decide(state)\n",
        encoding="utf-8",
    )

    findings = scan(root)

    assert [item.path for item in findings] == [
        "new_product_root/service.py"
    ]
    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


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

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]
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

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]
    assert "registry.get('decision').issue" in findings[0].detail


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

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


def test_aliased_decision_import_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/alias.py",
        source="from hidden import decide as choose\n",
    )

    assert [item.code for item in findings] == [
        "decision_authority_alias_import_outside_owner"
    ]


def test_decision_method_reference_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/reference.py",
        source=(
            "def bind(decision_core):\n"
            "    return decision_core.decide\n"
        ),
    )

    assert [item.code for item in findings] == [
        "decision_authority_reference_outside_owner"
    ]


def test_dynamic_decision_lookup_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/dynamic.py",
        source=(
            "def bind(decision_core):\n"
            "    return getattr(decision_core, 'decide')\n"
        ),
    )

    assert [item.code for item in findings] == [
        "dynamic_decision_authority_lookup_outside_owner"
    ]


def test_bare_decision_name_reference_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/name_reference.py",
        source=(
            "from hidden import decide\n"
            "choose = decide\n"
        ),
    )

    assert [item.code for item in findings] == [
        "decision_authority_name_reference_outside_owner"
    ]


def test_dunder_decision_lookup_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/dunder_lookup.py",
        source=(
            "def bind(decision_core):\n"
            "    return decision_core.__getattribute__('decide')\n"
        ),
    )

    assert [item.code for item in findings] == [
        "dynamic_decision_authority_lookup_outside_owner"
    ]


def test_dynamic_decision_mutation_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/mutation.py",
        source=(
            "def replace(decision_core, replacement):\n"
            "    setattr(decision_core, 'decide', replacement)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "dynamic_decision_authority_mutation_outside_owner"
    ]


def test_decision_dict_lookup_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/dict_lookup.py",
        source=(
            "def bind(decision_core):\n"
            "    return vars(decision_core)['decide']\n"
        ),
    )

    assert [item.code for item in findings] == [
        "subscript_decision_authority_lookup_outside_owner"
    ]


def test_generic_issue_method_remains_non_authoritative(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/certificates/service.py",
        source=(
            "def create(certificate_service, payload):\n"
            "    return certificate_service.issue(payload)\n"
        ),
    )

    assert findings == []


def test_decision_issue_method_is_blocked(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/issue.py",
        source=(
            "def run(decision_service, state):\n"
            "    return decision_service.issue(state)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


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


def test_contextual_external_optimizer_remains_non_authoritative(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/ads/tuner.py",
        source=(
            "def tune(optimizer, state):\n"
            "    return optimizer.optimize(state)\n"
        ),
    )

    assert findings == []


def test_direct_generic_optimize_call_remains_non_authoritative(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/ads/tuner.py",
        source=(
            "from math_tools import optimize\n"
            "def tune(state):\n"
            "    return optimize(state)\n"
        ),
    )

    assert findings == []


def test_contextual_shadow_planner_optimizer_is_blocked(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/feature/planner.py",
        source=(
            "class FeaturePlanner:\n"
            "    def run(self, state):\n"
            "        return self.shadow_planner.optimize(state)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


def test_exact_canonical_decision_owner_paths_remain_allowed(
    tmp_path: Path,
) -> None:
    for relative in (
        "core/ai/decision_core.py",
        "application/headless/decision_gateway.py",
        "demand_decision/canonical_decision_bridge.py",
        "runtime/decision_gateway.py",
        "runtime/decision_path_lock.py",
    ):
        findings = _scan_source(
            tmp_path=tmp_path,
            relative=relative,
            source=(
                "def run(decision_core, state):\n"
                "    return decision_core.decide(state)\n"
            ),
        )
        assert findings == [], relative


def test_new_core_ai_module_is_not_a_decision_owner(tmp_path: Path) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="core/ai/shadow_runtime.py",
        source=(
            "def run(decision_core, state):\n"
            "    return decision_core.decide(state)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


def test_new_decision_runtime_module_is_not_a_decision_owner(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="application/decision_runtime/shadow_runtime.py",
        source=(
            "def run(decision_core, state):\n"
            "    return decision_core.decide(state)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]


def test_near_miss_gateway_filename_is_not_an_owner(
    tmp_path: Path,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        relative="runtime/decision_gateway.py_backup.py",
        source=(
            "def run(decision_core, state):\n"
            "    return decision_core.decide(state)\n"
        ),
    )

    assert [item.code for item in findings] == [
        "possible_decision_core_bypass"
    ]
