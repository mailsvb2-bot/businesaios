from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORTS = {
    "RuntimeDecisionCore",
    "RuntimeDecisionExecutionService",
    "GovernanceChain",
    "ActionExecutor",
}
ALLOWED_PATH_FRAGMENTS = (
    "boot/",
    "tests/",
    "runtime/platform/support/",
)


def test_no_import_of_critical_runtime_classes_outside_boot() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS:
                        violations.append(
                            f"{normalized}:{node.lineno} imports forbidden runtime class '{alias.name}'"
                        )

    assert not violations, "\n".join(violations)
