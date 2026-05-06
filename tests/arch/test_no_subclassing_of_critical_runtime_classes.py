from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_BASES = {
    "DecisionCore",
    "GovernanceChain",
    "ActionExecutor",
}


def test_no_subclassing_of_critical_runtime_classes() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()
        if "tests/" in normalized:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            for base in node.bases:
                base_name = _base_name(base)
                if base_name in FORBIDDEN_BASES:
                    violations.append(
                        f"{normalized}:{node.lineno} subclasses sealed runtime class '{base_name}'"
                    )

    assert not violations, "\n".join(violations)


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
