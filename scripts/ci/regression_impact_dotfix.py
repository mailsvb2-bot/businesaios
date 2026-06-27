from __future__ import annotations

import os

from scripts.ci import regression_impact as _legacy


def normalize_path(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def blocked_artifact_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    offenders: list[str] = []
    for raw_path in paths:
        path = normalize_path(raw_path)
        padded = f"/{path}"
        if path.startswith(_legacy.GENERATED_ARTIFACT_PREFIXES) or path.endswith(_legacy.GENERATED_ARTIFACT_SUFFIXES):
            offenders.append(path)
            continue
        if any(part in padded for part in _legacy.GENERATED_ARTIFACT_PARTS):
            offenders.append(path)
    return tuple(sorted(set(offenders)))


def impacted_rules(paths: tuple[str, ...]):
    normalized = tuple(normalize_path(path) for path in paths)
    return tuple(rule for rule in _legacy.IMPACT_RULES if any(path.startswith(rule.prefixes) for path in normalized))


def required_fast_steps_for_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    steps: set[str] = set()
    for rule in impacted_rules(paths):
        steps.update(rule.required_fast_steps)
    return tuple(sorted(steps))


def missing_fast_steps_for_paths(paths: tuple[str, ...], fast_steps: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(required_fast_steps_for_paths(paths)) - set(fast_steps)))


def _changed_files_from_env() -> tuple[str, ...]:
    raw = os.environ.get("BAIOS_CHANGED_FILES", "")
    values = [part.strip() for part in raw.replace(",", "\n").splitlines()]
    return tuple(normalize_path(value) for value in values if value)


def changed_files() -> tuple[str, ...]:
    return _changed_files_from_env() or _legacy.changed_files()


__all__ = [
    "blocked_artifact_paths",
    "changed_files",
    "impacted_rules",
    "missing_fast_steps_for_paths",
    "normalize_path",
    "required_fast_steps_for_paths",
]
