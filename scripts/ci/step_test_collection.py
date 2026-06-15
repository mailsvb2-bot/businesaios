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
        "--collect-only",
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
        timeout=900,
        check=False,
    )

    output = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part).strip()
    if outcome.returncode != 0:
        tail = "\n".join(output.splitlines()[-140:])
        return False, "pytest collection failed\n" + tail
    collected = 0
    for line in output.splitlines():
        stripped = line.strip()
        if "::" in stripped:
            collected += 1
            continue
        if stripped.startswith("tests/") and ":" in stripped:
            maybe_number = stripped.rsplit(":", 1)[-1].strip()
            if maybe_number.isdigit():
                collected += int(maybe_number)
    return True, f"pytest collection passed; collected_items={collected}"


__all__ = ["run"]
