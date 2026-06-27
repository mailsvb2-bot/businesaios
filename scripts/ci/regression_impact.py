from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts.ci import step_ids as _step_ids
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command


@dataclass(frozen=True)
class ImpactRule:
    name: str
    prefixes: tuple[str, ...]
    required_fast_steps: tuple[str, ...]


StepNameFactory = Callable[[], str]


def _steps(*factories: StepNameFactory) -> tuple[str, ...]:
    return tuple(factory() for factory in factories)


IMPACT_RULES: tuple[ImpactRule, ...] = (
    ImpactRule(
        name="ci",
        prefixes=("scripts/ci/", ".github/workflows/", ".githooks/"),
        required_fast_steps=_steps(_step_ids.import_smoke, _step_ids.quality, _step_ids.lock_tests),
    ),
    ImpactRule(
        name="runtime",
        prefixes=("runtime/",),
        required_fast_steps=_steps(
            _step_ids.import_smoke,
            _step_ids.boot_smoke,
            _step_ids.architecture_bypass_scan,
            _step_ids.lock_tests,
        ),
    ),
    ImpactRule(
        name="storage",
        prefixes=("storage/",),
        required_fast_steps=_steps(_step_ids.import_smoke, _step_ids.lock_tests),
    ),
    ImpactRule(
        name="billing",
        prefixes=("billing/", "runtime/platform/billing"),
        required_fast_steps=_steps(_step_ids.import_smoke, _step_ids.lock_tests),
    ),
    ImpactRule(
        name="tenant-security",
        prefixes=("tenancy/", "security/", "runtime/tenancy/", "runtime/security/"),
        required_fast_steps=_steps(_step_ids.import_smoke, _step_ids.architecture_bypass_scan, _step_ids.lock_tests),
    ),
    ImpactRule(
        name="interfaces",
        prefixes=("interfaces/", "api/", "tests/interfaces/", "tests/api/"),
        required_fast_steps=_steps(_step_ids.import_smoke, _step_ids.boot_smoke, _step_ids.lock_tests),
    ),
)

GENERATED_ARTIFACT_PREFIXES: tuple[str, ...] = (
    "artifacts/",
    "dist/",
    ".pytest_cache/",
    "runtime/data/",
)
GENERATED_ARTIFACT_SUFFIXES: tuple[str, ...] = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
)
GENERATED_ARTIFACT_PARTS: tuple[str, ...] = (
    "/__pycache__/",
    "/.pytest_cache/",
)


def normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def blocked_artifact_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    offenders: list[str] = []
    for raw_path in paths:
        path = normalize_path(raw_path)
        padded = f"/{path}"
        if path.startswith(GENERATED_ARTIFACT_PREFIXES):
            offenders.append(path)
            continue
        if path.endswith(GENERATED_ARTIFACT_SUFFIXES):
            offenders.append(path)
            continue
        if any(part in padded for part in GENERATED_ARTIFACT_PARTS):
            offenders.append(path)
    return tuple(sorted(set(offenders)))


def impacted_rules(paths: tuple[str, ...]) -> tuple[ImpactRule, ...]:
    normalized = tuple(normalize_path(path) for path in paths)
    impacted: list[ImpactRule] = []
    for rule in IMPACT_RULES:
        if any(path.startswith(rule.prefixes) for path in normalized):
            impacted.append(rule)
    return tuple(impacted)


def required_fast_steps_for_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    steps: set[str] = set()
    for rule in impacted_rules(paths):
        steps.update(rule.required_fast_steps)
    return tuple(sorted(steps))


def missing_fast_steps_for_paths(paths: tuple[str, ...], fast_steps: tuple[str, ...]) -> tuple[str, ...]:
    required = set(required_fast_steps_for_paths(paths))
    present = set(fast_steps)
    return tuple(sorted(required - present))


def _changed_files_from_env() -> tuple[str, ...]:
    raw = os.environ.get("BAIOS_CHANGED_FILES", "")
    values = [part.strip() for part in raw.replace(",", "\n").splitlines()]
    return tuple(normalize_path(value) for value in values if value)


def _changed_files_from_git() -> tuple[str, ...]:
    root = repo_root()
    base_ref = os.environ.get("GITHUB_BASE_REF") or os.environ.get("BAIOS_BASE_REF") or "origin/main"
    candidate_commands = (
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
    )
    for command in candidate_commands:
        outcome = run_command(command, cwd=root, timeout=20, echo_output=False)
        if outcome.returncode == 0:
            paths = tuple(normalize_path(line) for line in outcome.stdout.splitlines() if line.strip())
            if paths:
                return paths
    return ()


def changed_files() -> tuple[str, ...]:
    return _changed_files_from_env() or _changed_files_from_git()


__all__ = [
    "GENERATED_ARTIFACT_PREFIXES",
    "GENERATED_ARTIFACT_SUFFIXES",
    "IMPACT_RULES",
    "ImpactRule",
    "blocked_artifact_paths",
    "changed_files",
    "impacted_rules",
    "missing_fast_steps_for_paths",
    "normalize_path",
    "required_fast_steps_for_paths",
]
