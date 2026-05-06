from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PATH_FRAGMENTS = (
    "boot/",
    "runtime/",
    "tests/",
)


def test_capability_access_only_in_boot_and_runtime() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "RuntimeCapabilityAccess":
                violations.append(
                    f"{normalized}:{node.lineno} contains forbidden RuntimeCapabilityAccess usage"
                )

    assert not violations, "\n".join(violations)
