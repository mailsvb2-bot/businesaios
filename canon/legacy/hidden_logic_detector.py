from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig
from canon.legacy.synonym_entity_registry import find_canonical_for


@dataclass(frozen=True)
class HiddenLogicFinding:
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


def _dict_contains_action_keys(node: ast.Dict, config: LegacyCanonConfig) -> bool:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return any(item in keys for item in config.hidden_logic_action_keys)


def scan_hidden_logic(config: LegacyCanonConfig) -> tuple[HiddenLogicFinding, ...]:
    findings: list[HiddenLogicFinding] = []

    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        if config.is_decision_surface(relpath):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name in config.forbidden_decision_class_names:
                    findings.append(
                        HiddenLogicFinding(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=node.name,
                            severity=FindingSeverity.CRITICAL,
                            reason="forbidden decision-brain class exists outside canonical DecisionCore",
                        )
                    )
                elif find_canonical_for(node.name) == "DecisionCore":
                    findings.append(
                        HiddenLogicFinding(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=node.name,
                            severity=FindingSeverity.MAJOR,
                            reason="DecisionCore synonym class exists outside canonical decision zone",
                        )
                    )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                if node.name in config.forbidden_decision_method_names:
                    findings.append(
                        HiddenLogicFinding(
                            relpath=relpath,
                            lineno=node.lineno,
                            symbol=node.name,
                            severity=FindingSeverity.CRITICAL,
                            reason="forbidden decision-emission method exists outside canonical path",
                        )
                    )
                    continue

                if any(lowered.startswith(prefix) for prefix in config.hidden_logic_return_hints):
                    for stmt in ast.walk(node):
                        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                            if _dict_contains_action_keys(stmt.value, config):
                                findings.append(
                                    HiddenLogicFinding(
                                        relpath=relpath,
                                        lineno=node.lineno,
                                        symbol=node.name,
                                        severity=FindingSeverity.CRITICAL,
                                        reason="function appears to construct/return final action payload outside canonical decision surface",
                                    )
                                )
                                break

    return tuple(sorted(findings, key=lambda item: (item.severity.value, item.relpath, item.lineno, item.symbol)))


__all__ = [
    "HiddenLogicFinding",
    "scan_hidden_logic",
]
