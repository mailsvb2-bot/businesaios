from __future__ import annotations

import shutil

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command


def run() -> tuple[bool, str]:
    cargo = shutil.which("cargo")
    if cargo is None:
        return False, "cargo is required for rust safety core gate"
    crate_dir = repo_root() / "rust" / "businessaios_safety_core"
    if not crate_dir.exists():
        return False, "rust safety core crate missing"
    outcome = run_command([cargo, "test", "--quiet"], timeout=180, cwd=crate_dir)
    if outcome.returncode != 0:
        return False, "rust safety core cargo tests failed"
    return True, "rust safety core cargo tests passed"


__all__ = ["run"]
