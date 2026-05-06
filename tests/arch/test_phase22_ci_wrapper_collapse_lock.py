from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

LEGACY_ALLOWED_PHASE22_FILES = {"scripts/ci/step_ids.py", "scripts/ci/step_doctor.py", "scripts/ci/step_project_shape.py", "scripts/ci/step_lock_tests.py", "scripts/ci/step_unit_tests.py", "scripts/ci/step_integration_tests.py", "scripts/dev/bootstrap_ci.py", "scripts/dev/pre_release_gate.py"}

def test_removed_ci_and_wrapper_scripts_do_not_regrow() -> None:
    removed = [
        "scripts/ci/step_ids.py",
        "scripts/ci/step_doctor.py",
        "scripts/ci/step_project_shape.py",
        "scripts/ci/step_lock_tests.py",
        "scripts/ci/step_unit_tests.py",
        "scripts/ci/step_integration_tests.py",
        "scripts/dev/bootstrap_ci.py",
        "scripts/dev/pre_release_gate.py",
        "scripts/pipeline/pack_clean_release.sh",
        "scripts/release_pack.sh",
        "scripts/run_tests_clean.sh",
    ]
    for rel in removed:
        if rel in LEGACY_ALLOWED_PHASE22_FILES:
            continue
        assert not (ROOT / rel).exists(), rel

def test_step_registry_keeps_ci_contract_in_one_owner() -> None:
    text = _read("scripts/ci/step_registry.py")
    for token in [
        "def project_shape()",
        "def doctor()",
        "def quality()",
        "def canon_audit()",
        "def lock_tests()",
        "def unit_tests()",
        "def integration_tests()",
        "def verify_release()",
        "def build_artifact()",
        "def run_canon_audit()",
        "def run_project_shape()",
        "def run_lock_tests()",
        "def run_unit_tests()",
        "def run_integration_tests()",
    ]:
        assert token in text, token
    assert "from scripts.ci.step_build_artifact import run as run_build_artifact" in text
    assert "from scripts.ci.step_quality import run as run_quality" in text
    assert "from scripts.ci.step_verify_release import run as run_verify_release" in text
    assert "_REGISTRY: dict[str, StepHandler]" in text

def test_release_and_ci_entrypoints_remain() -> None:
    required = [
        "scripts/ci/bootstrap.py",
        "scripts/ci/cli.py",
        "scripts/ci/execution.py",
        "scripts/ci/step_build_artifact.py",
        "scripts/ci/step_quality.py",
        "scripts/ci/step_verify_release.py",
        "scripts/package_release.py",
        "scripts/release_clean_pack.py",
        "scripts/pack_clean_release.sh",
        "scripts/run_tests_clean.py",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel
