from __future__ import annotations

import ast
from pathlib import Path

# Only these files may import runtime._internal.*
ALLOWLIST = {
    "runtime/executor.py",
    "runtime/effects/__init__.py",
    "runtime/execution/provider_outbound_sender.py",
}

IDENTITY_FACADE = "runtime/execution/provider_outbound_sender.py"
EFFECTS_BOUNDARY = "runtime/effects/__init__.py"


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


def test_provider_outbound_compatibility_exception_is_identity_only() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / IDENTITY_FACADE
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
    ]
    source = path.read_text(encoding="utf-8")
    assert "with allow_internal_import():" in source
    assert "sys.modules[__name__] = _OWNER" in source
    assert "importlib" not in source
    assert '"runtime._internal" +' not in source


def test_effects_boundary_has_one_explicit_guarded_internal_import() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / EFFECTS_BOUNDARY
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    internal_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and str(node.module or "").startswith("runtime._internal")
    ]
    assert len(internal_imports) == 1
    assert internal_imports[0].module == "runtime._internal.effects_clients.telegram_endpoint"

    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        if any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == "allow_internal_import"
            for item in node.items
        ):
            guarded = any(internal_import is child for child in ast.walk(node) for internal_import in internal_imports)
            if guarded:
                break
    assert guarded
