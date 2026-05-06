from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "ci"


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_only_cli_imports_execute_entrypoint() -> None:
    offenders: list[str] = []

    for path in _python_files(TARGET):
        if path.name == "execution.py":
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "scripts.ci.execution":
                if path.name != "cli.py":
                    offenders.append(str(path.relative_to(ROOT)))
                    break

    assert not offenders, f"execution imported outside cli.py: {offenders}"
