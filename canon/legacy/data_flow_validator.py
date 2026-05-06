from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig


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


def _forbidden_names_lower(config: LegacyCanonConfig) -> set[str]:
    return {item.lower() for item in config.forbidden_shadow_state_names}


def scan_shadow_state(config: LegacyCanonConfig) -> tuple[DataFlowViolation, ...]:
    findings: list[DataFlowViolation] = []
    forbidden = _forbidden_names_lower(config)

    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id.lower() in forbidden:
                findings.append(
                    DataFlowViolation(
                        relpath=relpath,
                        lineno=node.lineno,
                        symbol=node.id,
                        severity=FindingSeverity.CRITICAL,
                        reason="forbidden shadow-state identifier detected",
                    )
                )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower() in forbidden:
                findings.append(
                    DataFlowViolation(
                        relpath=relpath,
                        lineno=node.lineno,
                        symbol=node.value,
                        severity=FindingSeverity.MAJOR,
                        reason="forbidden shadow-state literal detected",
                    )
                )

    return tuple(sorted(findings, key=lambda item: (item.severity.value, item.relpath, item.lineno, item.symbol)))


def verify_single_state_source_files_exist(config: LegacyCanonConfig) -> tuple[DataFlowViolation, ...]:
    findings: list[DataFlowViolation] = []
    for relpath in config.canonical_state_files:
        path = config.repo_root / relpath
        if not path.exists():
            findings.append(
                DataFlowViolation(
                    relpath=relpath,
                    lineno=1,
                    symbol=relpath,
                    severity=FindingSeverity.CRITICAL,
                    reason="required canonical state surface is missing",
                )
            )
    return tuple(findings)


__all__ = [
    "DataFlowViolation",
    "scan_shadow_state",
    "verify_single_state_source_files_exist",
]
