from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from canon.collapse.decision_path_map import FindingSeverity, LegacyCanonConfig


@dataclass(frozen=True)
class DataFlowViolation:
    relpath: str
    lineno: int
    symbol: str
    severity: FindingSeverity
    reason: str


def _iter_python_files(config: LegacyCanonConfig) -> Iterable[Path]:
    for path in config.repo_root.rglob("*.py"):
        relpath = config.normalize_relpath(path)
        if config.is_included_relpath(relpath):
            yield path


def scan_shadow_state(config: LegacyCanonConfig) -> tuple[DataFlowViolation, ...]:
    findings: list[DataFlowViolation] = []
    forbidden = {item.lower() for item in config.forbidden_shadow_state_names}
    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id.lower() in forbidden:
                findings.append(DataFlowViolation(relpath, node.lineno, node.id, FindingSeverity.CRITICAL, "forbidden shadow-state identifier detected"))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower() in forbidden:
                findings.append(DataFlowViolation(relpath, node.lineno, node.value, FindingSeverity.MAJOR, "forbidden shadow-state literal detected"))
    return tuple(sorted(findings, key=lambda item: (item.severity.value, item.relpath, item.lineno, item.symbol)))


def verify_single_state_source_files_exist(config: LegacyCanonConfig) -> tuple[DataFlowViolation, ...]:
    return tuple(DataFlowViolation(relpath, 1, relpath, FindingSeverity.CRITICAL, "required canonical state surface is missing") for relpath in config.canonical_state_files if not (config.repo_root / relpath).exists())


__all__ = ["DataFlowViolation", "scan_shadow_state", "verify_single_state_source_files_exist"]
