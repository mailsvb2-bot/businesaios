from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imports_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.append(n.name)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                out.append(node.module)
    return out


def test_world_model_core_is_pure_no_platform_imports():
    pkg = ROOT / "core" / "economics" / "world_model"
    assert pkg.exists(), "world_model package must exist"
    bad = []
    for py in pkg.rglob("*.py"):
        for mod in _imports_in(py):
            if mod.startswith("runtime.platform") or mod.startswith("adapters") or mod.startswith("runtime"):
                bad.append((str(py), mod))
    assert not bad, f"core economics world_model must not depend on platform: {bad}"
