from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "ci"
FORBIDDEN_PREFIXES = (
    "core.ai.decision_core",
    "runtime.boot",
    "runtime.executor",
    "runtime.guard",
    "interfaces.telegram",
    "interfaces.web",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _import_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    if isinstance(node, ast.ImportFrom):
        return node.module
    return None


def test_ci_is_infrastructural_and_not_domain_coupled() -> None:
    offenders: list[str] = []
    for path in _python_files(TARGET):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = _import_name(node)
            if not name:
                continue
            if any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                offenders.append(str(path.relative_to(ROOT)))
                break
    assert not offenders, f"ci coupled to domain/runtime internals: {offenders}"
