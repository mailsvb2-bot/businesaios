from __future__ import annotations

from pathlib import Path

from tests._infra.tracked_files import tracked_files

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_jsonl_artifacts_are_not_tracked() -> None:
    offenders = tuple(
        path.relative_to(REPO_ROOT).as_posix()
        for path in tracked_files(REPO_ROOT, "runtime/data/**/*.jsonl")
    )
    assert offenders == ()
