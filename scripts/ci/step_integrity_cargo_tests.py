from __future__ import annotations

import re
import shutil

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import isolated_cargo_target, run_command


def _executed_test_count(output: str) -> int:
    counts = [int(match) for match in re.findall(r"running\s+(\d+)\s+tests?", output)]
    return sum(counts)


def run() -> tuple[bool, str]:
    root = repo_root()
    cargo = shutil.which("cargo")
    if cargo is None:
        return False, "cargo executable not found; Rust integrity core cannot be tested"

    manifest = root / "rust" / "businessaios_integrity_core" / "Cargo.toml"
    if not manifest.exists():
        return False, f"Rust integrity core manifest missing: {manifest.relative_to(root)}"

    with isolated_cargo_target("integrity-core") as cargo_env:
        outcome = run_command(
            [cargo, "test", "--manifest-path", str(manifest)],
            cwd=root,
            env=cargo_env,
            timeout=180,
            echo_output=False,
        )
    output = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part).strip()

    if outcome.returncode != 0:
        return False, "Rust integrity core cargo tests failed\n" + "\n".join(output.splitlines()[-100:])

    executed = _executed_test_count(output)
    if executed <= 0:
        return False, "Rust integrity core compiled but no Rust tests were executed"

    return True, f"Rust integrity core cargo tests passed; executed_tests={executed}"


__all__ = ["run", "_executed_test_count"]
