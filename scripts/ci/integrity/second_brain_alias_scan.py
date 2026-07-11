from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from scripts.ci.integrity import auditor

CANON_SECOND_BRAIN_ALIAS_SCAN = True


def _normalized(name: str) -> str:
    return "".join(ch for ch in str(name or "").casefold() if ch.isalnum())


def _looks_like_decision_authority_alias(name: str, executable_names: set[str]) -> bool:
    text = str(name or "")
    if text in executable_names:
        return True

    # Snake-case names such as `decision_core` are dependency/instance bindings,
    # not executable authority type surfaces. The scanner targets exported or
    # assignable authority aliases such as RuntimeDecisionCore/DecisionEngine.
    if not any(ch.isupper() for ch in text):
        return False

    normalized = _normalized(text)
    return any(
        token in normalized
        for token in (
            "decisioncore",
            "decisionengine",
            "plannerengine",
            "secondbrain",
            "shadowbrain",
            "alternatebrain",
            "localbrain",
        )
    )


def _assigned_names(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> tuple[ast.Name, ...]:
    targets: list[ast.AST]
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        targets = [node.target]

    names: list[ast.Name] = []
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.append(child)
    return tuple(names)


def _alias_findings_for_path(path: Path, spec: dict[str, Any]) -> list[auditor.Finding]:
    relative = auditor.rel(path)
    if relative.startswith("tests/") or relative in auditor.ALLOWED_NEGATIVE_BRAIN_GUARD_PATHS:
        return []
    if relative == auditor.CANONICAL_DECISION_CORE_PATH:
        return []

    tree = auditor.parse_file(path)
    if tree is None:
        return []

    executable_names = auditor._executable_decision_authority_names(spec)
    findings: list[auditor.Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is None:
                    continue
                if not _looks_like_decision_authority_alias(alias.asname, executable_names):
                    continue
                findings.append(
                    auditor.finding(
                        "P0_DECISION_AUTHORITY_ALIAS",
                        "P0",
                        "Executable decision authority import alias",
                        path,
                        getattr(node, "lineno", 1),
                        f"Import alias `{alias.name} as {alias.asname}` creates a competing decision-authority surface.",
                        "Import the canonical DecisionCore under its canonical name and keep runtime/services as non-authoritative callers.",
                    )
                )
            continue

        if not isinstance(node, ast.Assign | ast.AnnAssign | ast.NamedExpr):
            continue

        value = getattr(node, "value", None)
        if value is None:
            continue
        for target in _assigned_names(node):
            if not _looks_like_decision_authority_alias(target.id, executable_names):
                continue
            findings.append(
                auditor.finding(
                    "P0_DECISION_AUTHORITY_ALIAS",
                    "P0",
                    "Executable decision authority assignment alias",
                    path,
                    getattr(node, "lineno", 1),
                    f"Assignment to `{target.id}` can expose a second executable decision authority.",
                    "Delete the alias. Route all decision issuance through core.ai.decision_core.DecisionCore.",
                )
            )

    return findings


def check_decision_authority_aliases(files: list[Path], spec: dict[str, Any]) -> list[auditor.Finding]:
    findings: list[auditor.Finding] = []
    for path in files:
        findings.extend(_alias_findings_for_path(path, spec))
    return findings


__all__ = ["CANON_SECOND_BRAIN_ALIAS_SCAN", "check_decision_authority_aliases"]
