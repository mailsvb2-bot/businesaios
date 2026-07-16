from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from canon.anti_second_brain_rules import HARD_DECISION_AUTHORITY_METHODS
from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_exemptions import (
    is_bounded_non_runtime_regression_fixture,
    is_canonical_singleton_storage_assignment,
    is_fail_closed_runtime_decision_core_tripwire,
    is_registry_reference_accessor,
    module_exports,
)
from scripts.ci.integrity.decision_authority_alias_rules import (
    AUTHORITY_METHODS,
    assigned_names,
    class_method_names,
    is_authority_function_definition_name,
    is_authority_type_definition_name,
    is_non_executable_data_assignment,
    is_pure_authority_interface,
    looks_like_decision_authority_alias,
    parent_map,
    plain_frozen_data_type_names,
    value_can_expose_executable,
)

CANON_SECOND_BRAIN_ALIAS_SCAN = True


def _definition_finding(
    *,
    path: Path,
    node: ast.AST,
    name: str,
    kind: str,
    reason: str | None = None,
) -> auditor.Finding:
    message = reason or (
        f"{kind} `{name}` exposes a competing decision-authority surface "
        "outside canonical DecisionCore."
    )
    return auditor.finding(
        "P0_DECISION_AUTHORITY_DEFINITION",
        "P0",
        "Competing executable decision authority definition",
        path,
        getattr(node, "lineno", 1),
        message,
        "Delete the authority. Keep decision issuance exclusively in "
        "core.ai.decision_core.DecisionCore.",
    )


def _concrete_hard_authority_methods(node: ast.ClassDef) -> set[str]:
    return class_method_names(node) & HARD_DECISION_AUTHORITY_METHODS


def _alias_findings_for_path(
    path: Path,
    spec: dict[str, Any],
) -> list[auditor.Finding]:
    relative = auditor.rel(path)
    if (
        relative.startswith("tests/")
        or relative in auditor.ALLOWED_NEGATIVE_BRAIN_GUARD_PATHS
    ):
        return []
    if relative == auditor.CANONICAL_DECISION_CORE_PATH:
        return []

    tree = auditor.parse_file(path)
    if tree is None:
        return []

    executable_names = auditor._executable_decision_authority_names(spec)
    parents = parent_map(tree)
    plain_data_types = plain_frozen_data_type_names(tree)
    exported_names = module_exports(tree)
    findings: list[auditor.Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if is_fail_closed_runtime_decision_core_tripwire(
                relative=relative,
                node=node,
            ):
                continue
            if is_bounded_non_runtime_regression_fixture(
                relative=relative,
                node=node,
                exported_names=exported_names,
            ):
                continue
            if is_pure_authority_interface(node):
                continue

            hard_methods = _concrete_hard_authority_methods(node)
            if hard_methods:
                methods = ", ".join(sorted(hard_methods))
                findings.append(
                    _definition_finding(
                        path=path,
                        node=node,
                        name=node.name,
                        kind="Class",
                        reason=(
                            f"Class `{node.name}` defines concrete sovereign "
                            f"method(s) `{methods}` outside canonical DecisionCore."
                        ),
                    )
                )
                continue

            authority_methods = class_method_names(node) & AUTHORITY_METHODS
            if is_authority_type_definition_name(
                node.name,
                executable_names,
            ) or (
                authority_methods
                and looks_like_decision_authority_alias(
                    node.name,
                    executable_names,
                )
            ):
                findings.append(
                    _definition_finding(
                        path=path,
                        node=node,
                        name=node.name,
                        kind="Class",
                    )
                )
            continue

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if is_registry_reference_accessor(node, parents=parents):
                continue
            if (
                node.name in HARD_DECISION_AUTHORITY_METHODS
                or is_authority_function_definition_name(
                    node.name,
                    executable_names,
                )
            ):
                findings.append(
                    _definition_finding(
                        path=path,
                        node=node,
                        name=node.name,
                        kind="Function",
                    )
                )
            continue

        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is None:
                    continue
                if alias.name.isupper() and alias.asname.isupper():
                    continue
                if not looks_like_decision_authority_alias(
                    alias.asname,
                    executable_names,
                ):
                    continue
                findings.append(
                    auditor.finding(
                        "P0_DECISION_AUTHORITY_ALIAS",
                        "P0",
                        "Executable decision authority import alias",
                        path,
                        getattr(node, "lineno", 1),
                        f"Import alias `{alias.name} as {alias.asname}` creates "
                        "a competing decision-authority surface.",
                        "Import the canonical DecisionCore under its canonical "
                        "name and keep runtime/services as non-authoritative callers.",
                    )
                )
            continue

        if not isinstance(node, ast.Assign | ast.AnnAssign | ast.NamedExpr):
            continue

        value = getattr(node, "value", None)
        if value is None or not value_can_expose_executable(value):
            continue
        for target in assigned_names(node):
            if not looks_like_decision_authority_alias(
                target.id,
                executable_names,
            ):
                continue
            if is_non_executable_data_assignment(
                target=target,
                value=value,
                plain_data_types=plain_data_types,
            ):
                continue
            if is_canonical_singleton_storage_assignment(
                relative=relative,
                node=node,
                target=target,
                parents=parents,
            ):
                continue
            findings.append(
                auditor.finding(
                    "P0_DECISION_AUTHORITY_ALIAS",
                    "P0",
                    "Executable decision authority assignment alias",
                    path,
                    getattr(node, "lineno", 1),
                    f"Assignment to `{target.id}` can expose a second executable "
                    "decision authority.",
                    "Delete the alias. Route all decision issuance through "
                    "core.ai.decision_core.DecisionCore.",
                )
            )

    return findings


def check_decision_authority_aliases(
    files: list[Path],
    spec: dict[str, Any],
) -> list[auditor.Finding]:
    findings: list[auditor.Finding] = []
    for path in files:
        findings.extend(_alias_findings_for_path(path, spec))
    return findings


__all__ = ["CANON_SECOND_BRAIN_ALIAS_SCAN", "check_decision_authority_aliases"]
