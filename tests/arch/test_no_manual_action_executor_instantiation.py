from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SUFFIXES = (
    "boot/factories/action_executor_factory.py",
    "boot/registrations/register_action_executor.py",
)


def test_no_manual_action_executor_instantiation() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()
        if normalized.endswith(ALLOWED_SUFFIXES):
            continue
        if "tests/" in normalized:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) == "ActionExecutor":
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden ActionExecutor(...) instantiation"
                )

    assert not violations, "\n".join(violations)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return None
