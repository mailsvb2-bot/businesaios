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
        allowed_local_registry_lines = _typed_channel_registry_register_lines(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            target = _call_target(node)
            if target == "registry.register" and node.lineno not in allowed_local_registry_lines:
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden registry.register(...) usage"
                )

    assert not violations, "\n".join(violations)


def _typed_channel_registry_register_lines(tree: ast.AST) -> set[int]:
    allowed: set[int] = set()
    for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
        typed_registry_names: set[str] = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if _call_name(node.value) == "TypedChannelAdapterRegistry":
                    typed_registry_names.update(
                        target.id for target in node.targets if isinstance(target, ast.Name)
                    )
            if isinstance(node, ast.Call) and _call_target(node) in {
                f"{name}.register" for name in typed_registry_names
            }:
                allowed.add(node.lineno)
    return allowed


def _call_target(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != "register":
        return None
    if not isinstance(func.value, ast.Name):
        return None
    return f"{func.value.id}.register"


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None
