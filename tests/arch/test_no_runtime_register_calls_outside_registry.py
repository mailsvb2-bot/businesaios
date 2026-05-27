from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SUFFIXES = (
    "runtime/registry.py",
    "tests/arch/test_no_runtime_register_calls_outside_registry.py",
)
ALLOWED_PATH_FRAGMENTS = (
    "boot/registrations/",
    "interfaces/messaging_runtime/",
    "tests/",
)


def test_no_runtime_register_calls_outside_registry() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if normalized.endswith(ALLOWED_SUFFIXES):
            continue
        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            target = _call_target(node)
            if target == "registry.register":
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden registry.register(...) usage"
                )

    assert not violations, "\n".join(violations)


def _call_target(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != "register":
        return None
    if not isinstance(func.value, ast.Name):
        return None
    return f"{func.value.id}.register"
