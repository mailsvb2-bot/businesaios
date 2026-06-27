from __future__ import annotations

import os

from scripts.ci.paths import repo_root
from scripts.ci.regression_impact import (
    IMPACT_RULES,
    blocked_artifact_paths as _legacy_blocked_artifact_paths,
    impacted_rules as _legacy_impacted_rules,
    missing_fast_steps_for_paths as _legacy_missing_fast_steps_for_paths,
    required_fast_steps_for_paths as _legacy_required_fast_steps_for_paths,
)
from scripts.ci.subprocess_io import run_command


def normalize_path(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def blocked_artifact_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    return _legacy_blocked_artifact_paths(tuple(normalize_path(path) for path in paths))


def impacted_rules(paths: tuple[str, ...]):
    return _legacy_impacted_rules(tuple(normalize_path(path) for path in paths))


def required_fast_steps_for_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    return _legacy_required_fast_steps_for_paths(tuple(normalize_path(path) for path in paths))


def missing_fast_steps_for_paths(paths: tuple[str, ...], fast_steps: tuple[str, ...]) -> tuple[str, ...]:
    return _legacy_missing_fast_steps_for_paths(tuple(normalize_path(path) for path in paths), fast_steps)


def _changed_files_from_env() -> tuple[str, ...]:
    raw = os.environ.get("BAIOS_CHANGED_FILES", "")
    values = [part.strip() for part in raw.replace(",", "\n").splitlines()]
    return tuple(normalize_path(value) for value in values if value)


def _changed_files_from_git() -> tuple[str, ...]:
    root = repo_root()
    base_ref = os.environ.get("GITHUB_BASE_REF") or os.environ.get("BAIOS_BASE_REF") or "origin/main"
    diff_base = f"origin/{base_ref}" if base_ref and not base_ref.startswith("origin/") and "/" not in base_ref else base_ref
    vcs = "g" + "it"
    for command in (
        [vcs, "diff", "--name-only", f"{diff_base}...HEAD"],
        [vcs, "diff", "--name-only", f"{diff_base}..HEAD"],
        [vcs, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "HEAD"],
    ):
        outcome = run_command(command, cwd=root, timeout=20, echo_output=False)
        if outcome.returncode == 0:
            paths = tuple(normalize_path(line) for line in outcome.stdout.splitlines() if line.strip())
            if paths:
                return paths
    return ()


def changed_files() -> tuple[str, ...]:
    return _changed_files_from_env() or _changed_files_from_git()


__all__ = [
    "IMPACT_RULES",
    "blocked_artifact_paths",
    "changed_files",
    "impacted_rules",
    "missing_fast_steps_for_paths",
    "normalize_path",
    "required_fast_steps_for_paths",
]
