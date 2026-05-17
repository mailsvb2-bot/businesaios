from __future__ import annotations

import ast
import sys
from pathlib import Path

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import PYTEST_REQUIRED_PLUGINS, run_command


_TEST_DIRS = ("tests",)


class _AsyncTestVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.async_tests: list[tuple[int, str]] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("test_"):
            self.async_tests.append((int(node.lineno), str(node.name)))
        self.generic_visit(node)


def _find_async_tests(root: Path) -> list[str]:
    findings: list[str] = []
    for dirname in _TEST_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("test_*.py")):
            if any(part in {".git", ".venv", "__pycache__", "artifacts"} for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                findings.append(f"{path.relative_to(root).as_posix()}:syntax_error:{exc.lineno}")
                continue
            visitor = _AsyncTestVisitor()
            visitor.visit(tree)
            for lineno, name in visitor.async_tests:
                findings.append(f"{path.relative_to(root).as_posix()}:{lineno}:{name}")
    return findings


def run() -> tuple[bool, str]:
    root = repo_root()
    async_tests = _find_async_tests(root)
    if not async_tests:
        return True, "no async tests discovered"

    missing_plugins: list[str] = []
    for plugin in PYTEST_REQUIRED_PLUGINS:
        outcome = run_command([
            sys.executable,
            "-c",
            f"import {plugin}; print('{plugin}:ok')",
        ], timeout=20)
        if outcome.returncode != 0:
            missing_plugins.append(plugin)
    if missing_plugins:
        return False, "missing required pytest async plugin(s): " + ", ".join(missing_plugins)

    outcome = run_command([
        sys.executable,
        "-c",
        "import pytest_asyncio; print('pytest_asyncio_available')",
    ], timeout=20)
    if outcome.returncode != 0:
        return False, "pytest-asyncio is not importable"

    return True, f"async test contract passed; async_tests={len(async_tests)} required_plugins={','.join(PYTEST_REQUIRED_PLUGINS)}"


__all__ = ["run"]
