from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PATH_FRAGMENTS = (
    "boot/",
    "runtime/",
    "tests/",
)


def test_registry_access_is_not_used_outside_boot() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            target = _call_target(node)
            if target == "registry.get":
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden registry.get(...) usage"
                )

    assert not violations, "\n".join(violations)


def _call_target(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != "get":
        return None
    if not isinstance(func.value, ast.Name):
        return None
    return f"{func.value.id}.get"
