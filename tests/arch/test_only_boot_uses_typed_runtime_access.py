from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PATH_FRAGMENTS = (
    "boot/",
    "tests/",
)


def test_only_boot_uses_typed_runtime_access() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "RuntimeTypedAccess":
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden RuntimeTypedAccess usage"
                )

    assert not violations, "\n".join(violations)
