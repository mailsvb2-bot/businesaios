from __future__ import annotations

import ast
from pathlib import Path


MEMORY_FILES = [
    Path("application/memory/business_operating_memory.py"),
    Path("application/memory/business_memory_compactor.py"),
    Path("execution/business_operating_memory.py"),
    Path("execution/business_memory_projection.py"),
    Path("execution/business_memory_compactor.py"),
]


FORBIDDEN_IMPORT_ROOTS = {
    "DecisionCore",
    "ActionExecutor",
    "EffectExecutor",
}

FORBIDDEN_IMPORT_MODULE_FRAGMENTS = {
    "decision_core",
    "action_executor",
    "effect_executor",
    "runtime.executor",
}

FORBIDDEN_CALL_NAMES = {
    "issue_decision",
    "unlock_effect",
    "execute_action",
    "decide",
}


def _load_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))


def test_business_memory_layer_has_no_decision_or_effect_imports() -> None:
    violations: list[str] = []

    for path in MEMORY_FILES:
        if not path.exists():
            continue

        tree = _load_tree(path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if any(fragment in imported for fragment in FORBIDDEN_IMPORT_MODULE_FRAGMENTS):
                        violations.append(f"{path}:{node.lineno}: import {imported}")

            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(fragment in module for fragment in FORBIDDEN_IMPORT_MODULE_FRAGMENTS):
                    violations.append(f"{path}:{node.lineno}: from {module} import ...")

                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(f"{path}:{node.lineno}: imports {alias.name}")

    assert violations == []


def test_business_memory_layer_does_not_call_decision_or_effect_functions() -> None:
    violations: list[str] = []

    for path in MEMORY_FILES:
        if not path.exists():
            continue

        tree = _load_tree(path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = None
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr

            if call_name in FORBIDDEN_CALL_NAMES:
                violations.append(f"{path}:{node.lineno}: calls {call_name}")

    assert violations == []


def test_business_memory_payloads_are_explicitly_evidence_only() -> None:
    required_markers = {
        "evidence_only",
        "must_not_issue_decision",
        "must_not_unlock_effects",
    }

    checked_files = [
        Path("application/memory/business_operating_memory.py"),
        Path("execution/business_memory_projection.py"),
    ]

    missing: list[str] = []

    for path in checked_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in required_markers:
            if marker not in text:
                missing.append(f"{path}: missing {marker}")

    assert missing == []
