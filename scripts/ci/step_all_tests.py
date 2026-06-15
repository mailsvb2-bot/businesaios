from __future__ import annotations

import subprocess
import sys

from scripts.ci.paths import repo_root


def run() -> tuple[bool, str]:
    root = repo_root()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--import-mode=importlib",
        "-q",
        "-p",
        "pytest_asyncio.plugin",
        "tests",
    ]
    outcome = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=3600,
        check=False,
    )

    output = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part).strip()
    if outcome.returncode != 0:
        tail = "\n".join(output.splitlines()[-160:])
        return False, "all pytest suite failed\n" + tail
    return True, "all pytest suite passed"


__all__ = ["run"]
