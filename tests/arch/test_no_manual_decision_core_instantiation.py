from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SUFFIXES = (
    "boot/factories/decision_core_factory.py",
    "boot/registrations/register_decision_core.py",
    "runtime/boot/boot_core_assembly.py",
)
FORBIDDEN_RUNTIME_DECISION_CLASSES = {
    "RuntimeDecisionCore",
    "RuntimeDecisionExecutionService",
}


def test_no_manual_decision_core_instantiation() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()
        if normalized.endswith(ALLOWED_SUFFIXES):
            continue
        if "tests/" in normalized:
            continue
        if "runtime/platform/support/" in normalized:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in FORBIDDEN_RUNTIME_DECISION_CLASSES:
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden runtime decision execution service instantiation"
                )

    assert not violations, "\n".join(violations)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return None
