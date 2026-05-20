from __future__ import annotations

import json
import shutil

from application.business_autonomy.safety_core_diagnostics import write_safety_core_parity_evidence
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command


def run() -> tuple[bool, str]:
    cargo = shutil.which("cargo")
    if cargo is None:
        return False, "cargo is required for rust safety core gate"
    root = repo_root()
    crate_dir = root / "rust" / "businessaios_safety_core"
    if not crate_dir.exists():
        return False, "rust safety core crate missing"
    test_outcome = run_command([cargo, "test", "--quiet"], timeout=180, cwd=crate_dir)
    if test_outcome.returncode != 0:
        return False, "rust safety core cargo tests failed"
    fixture_path = root / "safety_fixtures" / "businessaios_safety_core_golden.json"
    fixture_outcome = run_command(
        [cargo, "run", "--quiet", "--bin", "safety_fixture_runner", "--", "--json", str(fixture_path)],
        timeout=180,
        cwd=crate_dir,
    )
    if fixture_outcome.returncode != 0:
        return False, "rust safety core shared fixture runner failed"
    try:
        report = json.loads(fixture_outcome.stdout.strip())
    except json.JSONDecodeError:
        return False, "rust safety core shared fixture runner returned invalid json"
    if report.get("passed") is not True:
        return False, "rust safety core shared fixture runner reported drift"
    artifact_path = write_safety_core_parity_evidence(repo_root=root)
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "rust safety core parity artifact is unreadable"
    if artifact.get("passed") is not True or artifact.get("drift_detected") is not False:
        return False, "rust safety core parity artifact reported drift"
    return True, f"rust safety core cargo tests, property tests, shared fixture json parity, and evidence artifact passed: {artifact_path.relative_to(root).as_posix()}"


__all__ = ["run"]
