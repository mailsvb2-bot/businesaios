"""Guardrail: production code must not import experimental/examples.

This is a *static* check to prevent accidental wiring of demo code into prod.
"""

from __future__ import annotations

import ast
import pathlib

PROD_DIRS = {
    "core",
    "governance",
    "infra",
    "runtime",
    "services",
    "ml",
    "formal",
}


def _iter_prod_py_files(root: pathlib.Path):
    for d in PROD_DIRS:
        base = root / d
        if not base.exists():
            continue
        yield from base.rglob("*.py")
    # Also include main entrypoint.
    mp = root / "main.py"
    if mp.exists():
        yield mp


def test_no_imports_from_experimental_or_examples():
    root = pathlib.Path(__file__).resolve().parents[1]

    bad: list[tuple[str, int, str]] = []

    for path in _iter_prod_py_files(root):
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            # compileall will catch syntax; keep this test focused.
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith("experimental") or name.startswith("examples"):
                        bad.append((str(path.relative_to(root)), node.lineno, name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.startswith("experimental") or mod.startswith("examples"):
                    bad.append((str(path.relative_to(root)), node.lineno, mod))

    assert not bad, "Forbidden imports found:\n" + "\n".join(
        f"{p}:{ln} -> {m}" for p, ln, m in bad
    )
