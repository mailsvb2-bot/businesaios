from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _class_owners(name: str) -> list[str]:
    owners = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("tests/", ".git/", ".venv/", "venv/")):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=relative)
        if any(isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(tree)):
            owners.append(relative)
    return sorted(owners)


def test_phase16_experiment_service_has_single_domain_owner():
    assert _class_owners("ExperimentsService") == ["core/experiments/service.py"]
    owner = (ROOT / "core/experiments/__canon_domain__.py").read_text(encoding="utf-8")
    assert 'CANON_DOMAIN_NAME = "experiments"' in owner
    assert "CANON_DECISION_ISSUANCE_ALLOWED = False" in owner


def test_phase16_reuses_event_spine_not_parallel_database():
    source = (
        ROOT / "core/experiments/repositories/event_store_repository.py"
    ).read_text(encoding="utf-8")
    assert "append_event_strict" in source
    assert "iter_events_strict" in source
    assert "sqlite3" not in source
    assert "psycopg" not in source
    assert "Path(" not in source
    assert "open(" not in source


def test_phase16_autonomous_launch_cannot_use_legacy_runner():
    runtime_handler = (
        ROOT / "runtime/handlers/experiments_build.py"
    ).read_text(encoding="utf-8")
    legacy = (
        ROOT / "execution/runners/internal/create_experiment.py"
    ).read_text(encoding="utf-8")
    catalog = (
        ROOT / "runtime/boot_impl/actions_catalog.py"
    ).read_text(encoding="utf-8")

    assert "CREATE_EXPERIMENT_DECISION_ENVELOPE_REQUIRED" in runtime_handler
    assert "contract_v2" in runtime_handler
    assert "policy_governed" in runtime_handler
    assert "CREATE_EXPERIMENT_REQUIRES_CANONICAL_RUNTIME_ACTION" in legacy
    assert "ACTION_CREATE_EXPERIMENT_V1" in catalog


def test_phase16_legacy_experiment_surfaces_are_compatibility_only():
    legacy_package = (ROOT / "experimentation/__init__.py").read_text(encoding="utf-8")
    legacy_result = (ROOT / "contracts/experiment_result.py").read_text(encoding="utf-8")

    assert "CANON_EXPERIMENTATION_PACKAGE_OWNER = False" in legacy_package
    assert "CANON_EXPERIMENTATION_COMPAT_SHIM = True" in legacy_package
    assert "class Experiment:" not in legacy_package
    assert "class ExperimentRegistry:" not in legacy_package
    assert "class ExperimentEvaluator:" not in legacy_package
    assert "CANON_COMPAT_SHIM = True" in legacy_result
    assert "class ExperimentResult:" not in legacy_result
    assert "ExperimentResult = LegacyExperimentResult" in legacy_result


def test_phase16_canonical_result_has_one_physical_class_owner():
    assert _class_owners("ExperimentResult") == ["core/experiments/types.py"]
