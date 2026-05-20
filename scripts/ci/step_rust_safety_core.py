from __future__ import annotations

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
        [cargo, "run", "--quiet", "--bin", "safety_fixture_runner", "--", str(fixture_path)],
        timeout=180,
        cwd=crate_dir,
    )
    if fixture_outcome.returncode != 0:
        return False, "rust safety core shared fixture runner failed"
    return True, "rust safety core cargo tests and shared fixtures passed"


__all__ = ["run"]
