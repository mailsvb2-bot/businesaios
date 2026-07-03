from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_FILES = (
    "tools/canon_audit.py",
    "scripts/ci/integrity/auditor.py",
)
FORBIDDEN = tuple(
    ".".join(parts)
    for parts in (
        ("core", "ai", "decision_core"),
        ("core", "decision_core"),
        ("runtime", "executor"),
        ("runtime", "guard"),
    )
)


def _modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_audit_tools_do_not_import_decision_runtime_authority() -> None:
    for rel in AUDIT_FILES:
        modules = _modules(ROOT / rel)
        for blocked in FORBIDDEN:
            assert blocked not in modules
            assert not any(module.startswith(blocked + ".") for module in modules)
