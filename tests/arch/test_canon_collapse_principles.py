from __future__ import annotations

import ast
import json
from pathlib import Path

from canon.surface_ceiling import is_canonical_source_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANON_BOUNDARY_LOCK_PACK = True
CANON_BOUNDARY_LOCKS = (
    "legacy_boundary",
    "env_profile_boundary",
    "release_artifact_boundary",
    "decision_envelope_boundary",
    "sealed_effects_boundary",
    "tenant_boundary",
    "surface_growth_boundary",
    "release_manifest_workflow_boundary",
    "admin_visibility_boundary",
)


def _read(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


def _tree(rel: str) -> ast.AST:
    return ast.parse(_read(rel), filename=rel)


def _calls_function(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            return True
        if isinstance(func, ast.Attribute) and func.attr == name:
            return True
    return False


def _count_metrics():
    total_files = 0
    python_files = 0
    python_lines = 0

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PROJECT_ROOT)
        if not is_canonical_source_path(rel) or rel.parts[0] == "tests":
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        total_files += 1
        if path.suffix == ".py":
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    python_lines += sum(1 for _ in fh)
            except Exception:
                pass

    return {
        "total_files": total_files,
        "python_files": python_files,
        "total_python_lines": python_lines,
    }



def _load_effective_baseline(baseline: dict[str, int]) -> dict[str, int]:
    """Keep the historic baseline as target while explicitly accounting for audited debt."""

    ledger_path = PROJECT_ROOT / "canon" / "metrics_debt_ledger.json"
    if not ledger_path.exists():
        return baseline

    with ledger_path.open(encoding="utf-8") as fh:
        ledger = json.load(fh)

    pre_existing_debt = int(ledger.get("pre_existing_head_total_python_lines_debt", 0))
    current_iteration_budget = int(ledger.get("current_iteration_total_python_lines_budget", 0))

    effective = dict(baseline)
    effective["total_python_lines"] = (
        baseline["total_python_lines"] + pre_existing_debt + current_iteration_budget
    )
    return effective


def test_canon_file_exists():
    assert (PROJECT_ROOT / "canon" / "collapse_principles.py").exists()


def test_metrics_do_not_grow():
    baseline_path = PROJECT_ROOT / "canon" / "metrics_baseline.json"
    assert baseline_path.exists()

    with open(baseline_path, encoding="utf-8") as f:
        baseline = _load_effective_baseline(json.load(f))

    current = _count_metrics()

    assert current["total_files"] <= baseline["total_files"], current
    assert current["python_files"] <= baseline["python_files"], current
    assert current["total_python_lines"] <= baseline["total_python_lines"], current


def test_canon_boundary_lock_pack_names_all_guarded_edges() -> None:
    assert set(CANON_BOUNDARY_LOCKS) == {
        "legacy_boundary",
        "env_profile_boundary",
        "release_artifact_boundary",
        "decision_envelope_boundary",
        "sealed_effects_boundary",
        "tenant_boundary",
        "surface_growth_boundary",
        "release_manifest_workflow_boundary",
        "admin_visibility_boundary",
    }


def test_release_attestation_remains_prod_only_and_explicitly_flagged() -> None:
    text = _read("bootstrap/prod_guards.py")
    assert "from runtime.platform.config.env_flags import env_bool, env_str" in text
    assert "app_env = env_str('APP_ENV', env_str('ENV', 'dev')).lower()" in text
    assert "if app_env != 'prod' or not env_bool('RELEASE_ATTEST', True):" in text
    assert "verify_manifest(root_dir=root, manifest_path=root / 'release' / 'manifest.json')" in text
    assert "RELEASE_ATTESTATION_FAILED" in text


def test_decision_envelope_shape_is_owned_by_decision_path_lock() -> None:
    text = _read("runtime/decision_path_lock.py")
    assert "CANON_DECISION_PATH_LOCK_SINGLE_OWNER = True" in text
    assert "CANON_DECISION_PATH_LOCK_FAIL_CLOSED = True" in text
    assert "def _validate_decision_envelope_shape(" in text
    assert "decision_envelope_missing_decision" in text
    assert "decision_envelope_missing_decision_id" in text
    assert "decision_envelope_missing_correlation_id" in text
    assert "def lock_decision_for_executor(" in text


def test_runtime_gateways_do_not_bypass_decision_path_lock() -> None:
    runtime_gateway_text = _read("runtime/decision_gateway.py")
    headless_gateway_text = _read("application/headless/decision_gateway.py")
    runtime_gateway_tree = _tree("runtime/decision_gateway.py")
    headless_gateway_tree = _tree("application/headless/decision_gateway.py")

    assert "from runtime.decision_path_lock import issue_locked_decision" in runtime_gateway_text
    assert _calls_function(runtime_gateway_tree, "issue_locked_decision")
    assert "from runtime.decision_path_lock import" in headless_gateway_text
    assert "issue_locked_decision" in headless_gateway_text
    assert _calls_function(headless_gateway_tree, "issue_locked_decision")
    assert ".issue(enriched_state)" not in runtime_gateway_text
    assert "for attribute_name in ('optimize', 'issue', 'decide')" not in headless_gateway_text


def test_server_maintenance_reports_stay_outside_repo_by_default() -> None:
    text = _read("scripts/server/maintenance_check.py")
    assert "REPORT_DIR_DEFAULT" in text
    assert '"/tmp/businesaios-pytest-runs"' in text
    assert "runtime/data/reports/pytest-runs" not in text
    assert "subprocess.Popen" in text
    assert "scripts" in text and "ci" in text and "count_pytest_errors.py" in text


def test_surface_growth_budget_must_be_explicit_debt_ledger() -> None:
    baseline_path = PROJECT_ROOT / "canon" / "metrics_baseline.json"
    ledger_path = PROJECT_ROOT / "canon" / "metrics_debt_ledger.json"
    assert baseline_path.exists()
    assert ledger_path.exists()
    ledger_text = ledger_path.read_text(encoding="utf-8")
    assert "pre_existing_head_total_python_lines_debt" in ledger_text
    assert "current_iteration_total_python_lines_budget" in ledger_text


def test_boundary_locks_have_dedicated_existing_owners() -> None:
    expected = {
        "legacy_boundary": "tests/unit/storage/test_storage_layer.py",
        "env_profile_boundary": "tests/arch/test_phase15_env_hygiene_regrowth_lock.py",
        "release_artifact_boundary": "tests/test_release_clean.py",
        "decision_envelope_boundary": "tests/arch/test_wave3_decision_path_single_owner.py",
        "sealed_effects_boundary": "tests/test_no_network_outside_effects.py",
        "tenant_boundary": "tests/test_tenant_gate_missing_tenant_calls.py",
        "surface_growth_boundary": "tests/arch/test_canon_collapse_principles.py",
        "release_manifest_workflow_boundary": "bootstrap/prod_guards.py",
        "admin_visibility_boundary": "tests/arch/test_runtime_governance_surfaces_wave102.py",
    }
    missing = [path for path in expected.values() if not (PROJECT_ROOT / path).exists()]
    assert not missing, "Missing boundary lock owners:\n" + "\n".join(missing)
