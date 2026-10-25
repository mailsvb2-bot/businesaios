"""Fail closed when critical security tests disappear from the mandatory CI route."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.ci.config import project_shape_config
from scripts.ci.plan_registry import plan_for_gate

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci-fast.yml"
SECURITY_MODULES = (
    "tests/business_critical/test_execute_once_ledger_contract.py",
    "tests/business_critical/test_tenant_negative_contracts.py",
    "tests/business_critical/test_owner_only_authz_matrix.py",
    "tests/business_critical/test_router_schema_contract_all_routes.py",
    "tests/business_critical/test_effect_router_telegram_media_contract.py",
    "tests/unit/business_flows/test_event_links_registration_status.py",
)
THIS_TEST = "tests/lock/test_critical_security_ci_wiring.py"


def test_critical_security_tests_are_real_and_in_mandatory_fast_workflow() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = "      - name: Enforce tenant, authorization and execution security contracts"
    assert workflow.count(marker) == 1, "Mandatory security step missing or duplicated"
    section = workflow.split(marker, 1)[1].split("      - name:", 1)[0]
    assert "python -m pytest" in section, "Security step must execute pytest"
    assert " -m " not in section.replace("python -m pytest", ""), "Do not silently deselect security tests with pytest markers"
    for module in SECURITY_MODULES:
        assert section.count(module) == 1, f"Mandatory CI stopped executing {module}"
        source = ROOT / module
        assert source.is_file(), f"Critical test missing: {module}"
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=module)
        assert any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(tree)
        ), f"No executable test functions in {module}"


def test_fast_and_full_gates_retain_critical_test_coverage() -> None:
    config = project_shape_config(ROOT)
    assert THIS_TEST in config.lock_targets, "Security wiring watchdog must itself run in lock-tests"
    fast = {step.name for step in plan_for_gate("fast").steps}
    full = {step.name for step in plan_for_gate("full").steps}
    assert "lock-tests" in fast and "lock-tests" in full
    assert {"business-critical-tests", "unit-tests"} <= full
    business_runner = (ROOT / "scripts/ci/step_business_critical_tests.py").read_text(encoding="utf-8")
    unit_runner = (ROOT / "scripts/ci/config.py").read_text(encoding="utf-8")
    assert 'target_args=["tests/business_critical"]' in business_runner
    assert '"tests/unit"' in unit_runner
    assert "python -m scripts.ci.cli --gate fast" in WORKFLOW.read_text(encoding="utf-8")
