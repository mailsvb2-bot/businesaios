from __future__ import annotations

import ast
from pathlib import Path


# Only these files may import runtime._internal.*
ALLOWLIST = {
    "runtime/executor.py",
    # If you truly need it elsewhere, add explicitly, but keep it minimal.
    # "runtime/_internal/__init__.py",
}


FORBIDDEN_PREFIXES = (
    "runtime._internal",
    "runtime/_internal",  # in case someone does weird string-based checks
)


def _relpath(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _has_forbidden_import(tree: ast.AST) -> bool:
    # Static imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("runtime._internal"):
                    return True

        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("runtime._internal"):
                return True

        # Also catch obvious dynamic import patterns:
        # importlib.import_module("runtime._internal.x")
        if isinstance(node, ast.Call):
            # __import__("runtime._internal.x")
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    s = node.args[0].value
                    if s.startswith("runtime._internal"):
                        return True

            # importlib.import_module("runtime._internal.x")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    s = node.args[0].value
                    if s.startswith("runtime._internal"):
                        return True

    return False


def test_no_runtime_internal_imports_outside_executor():
    root = Path(__file__).resolve().parents[1]

    offenders: list[str] = []
    for p in root.rglob("*.py"):
        rel = _relpath(root, p)

        # Ignore tests themselves (tests can mention internal modules in strings, etc.)
        if rel.startswith("tests/"):
            continue

        # The sealed implementation zone is allowed to reference runtime._internal.
        if rel.startswith("runtime/_internal/"):
            continue

        if rel in ALLOWLIST:
            continue

        src = p.read_text(encoding="utf-8", errors="ignore")
        # quick prefilter for speed
        if "runtime._internal" not in src and "import_module" not in src and "__import__" not in src:
            continue

        try:
            tree = ast.parse(src)
        except SyntaxError:
            # If you want to enforce parseability, fail here instead.
            continue

        if _has_forbidden_import(tree):
            offenders.append(rel)

    assert not offenders, (
        "Forbidden imports of runtime._internal detected outside runtime/executor.py.\n"
        "Move the import into runtime/executor.py and access effects only via EffectsPort.\n"
        "Offenders:\n- " + "\n- ".join(offenders)
    )
