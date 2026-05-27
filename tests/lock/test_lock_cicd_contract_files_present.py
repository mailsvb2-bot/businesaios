from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


REQUIRED = [
    "scripts/ci/contracts.py",
    "scripts/ci/config.py",
    "scripts/ci/goal.py",
    "scripts/ci/paths.py",
    "scripts/ci/subprocess_io.py",
    "scripts/ci/reports.py",
    "scripts/ci/timing.py",
    "scripts/ci/makefile_tools.py",
    "scripts/ci/artifact_manifest.py",
    "scripts/ci/summary.py",
    "scripts/ci/junit_report.py",
    "scripts/ci/coverage_report.py",
    "scripts/ci/bootstrap.py",
    "scripts/ci/install_hooks.py",
    "scripts/ci/pytest_tools.py",
    "scripts/ci/doctor.py",
    "scripts/ci/check_requirements_lock.py",
    "scripts/ci/step_doctor.py",
    "scripts/ci/plan_registry.py",
    "scripts/ci/step_registry.py",
    "scripts/ci/execution.py",
    "scripts/ci/cli.py",
    "scripts/ci/step_project_shape.py",
    "scripts/ci/step_quality.py",
    "scripts/ci/step_lock_tests.py",
    "scripts/ci/step_unit_tests.py",
    "scripts/ci/step_integration_tests.py",
    "scripts/ci/step_verify_release.py",
    "scripts/ci/step_build_artifact.py",
    ".githooks/pre-push",
    "scripts/dev/pre_release_gate.py",
    "scripts/dev/bootstrap_ci.py",
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/ci-full.yml",
    ".github/workflows/release.yml",
    ".github/workflows/docker-image.yml",
    "docs/CI_CD_CANON_V7_PROJECT.md",
    "pytest.ini",
]


def test_cicd_contract_files_present() -> None:
    missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
    assert not missing, f"missing ci/cd contract files: {missing}"
