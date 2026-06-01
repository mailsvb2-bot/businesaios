"""Test: enforce canonical import paths.

Prevents the proliferation of duplicate modules.
All new code must import from canonical locations.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

# Canonical locations → deprecated aliases that must not grow new dependents.
DEPRECATED_IMPORT_PATHS = {
    "core.products.product_contract": "contracts.product_contract",
    "core.contracts.product_contract": "contracts.product_contract",
    "core.survival.controller": "survival.controller",
    "core.survival.metrics": "survival.metrics",
}

# Known legacy files that still use deprecated paths (frozen; must not grow).
LEGACY_ALLOWLIST = {
    "core/products/product_contract_compat.py",
    "core/contracts/__init__.py",
    "core/survival/__init__.py",
    "core/governance/__init__.py",
    "tests/arch/test_contract_alias_shims.py",
    "tests\\arch\\test_contract_alias_shims.py",
}

ROOT = Path(__file__).resolve().parents[1]


def _collect_imports(filepath: Path) -> list[str]:
    """Extract all import paths from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except Exception:
        return []

    paths: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            paths.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                paths.append(alias.name)
    return paths


def test_no_new_deprecated_imports():
    """New code must not import from deprecated module paths."""
    violations: list[str] = []

    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".venv", "node_modules"}]
        for f in files:
            if not f.endswith(".py"):
                continue
            filepath = Path(dirpath) / f
            rel = str(filepath.relative_to(ROOT))

            if rel in LEGACY_ALLOWLIST:
                continue

            for imp in _collect_imports(filepath):
                if imp in DEPRECATED_IMPORT_PATHS:
                    canonical = DEPRECATED_IMPORT_PATHS[imp]
                    violations.append(
                        f"  {rel}: uses '{imp}' → should be '{canonical}'"
                    )

    assert not violations, (
        f"Found {len(violations)} imports from deprecated paths:\n"
        + "\n".join(violations)
        + "\n\nFix: change to canonical import path."
    )


def test_shim_modules_are_reexport_only():
    """Shim modules must contain only re-exports, no new definitions."""
    shim_files = [
        ROOT / "core" / "survival" / "__init__.py",
    ]

    for path in shim_files:
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text())
        except Exception:
            continue

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                raise AssertionError(
                    f"{path.relative_to(ROOT)} is a shim but defines "
                    f"'{node.name}' — move definitions to canonical location."
                )
