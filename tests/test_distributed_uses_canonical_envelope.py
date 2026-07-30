from __future__ import annotations

import ast
from pathlib import Path


def test_distributed_imports_only_canonical_envelope():
    repo = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in repo.rglob("*distributed*.py"):
        rel = path.relative_to(repo).as_posix()
        if rel.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        if "core.decision.envelope" in modules:
            offenders.append(rel)
    assert not offenders, f"retired distributed envelope imports: {offenders}"
