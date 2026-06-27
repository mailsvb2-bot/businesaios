from __future__ import annotations

import subprocess


def _tracked(pattern: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "ls-files", pattern],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def test_runtime_jsonl_artifacts_are_not_tracked() -> None:
    offenders = _tracked("runtime/data/**/*.jsonl")
    assert offenders == ()
