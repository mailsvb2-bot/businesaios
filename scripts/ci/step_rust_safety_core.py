from __future__ import annotations

import json
import shutil

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
    return True, "rust safety core cargo tests, property tests, and shared fixture json parity passed"


__all__ = ["run"]
