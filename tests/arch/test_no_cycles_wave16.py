from __future__ import annotations

import ast
from pathlib import Path


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_env_flags_does_not_import_boot_modules() -> None:
    imports = _imports(Path("runtime/platform/config/env_flags.py"))
    assert not any(name.startswith("runtime.boot") or name == "boot" for name in imports)


def test_boot_package_init_only_uses_importlib_for_direct_owner_loading() -> None:
    imports = _imports(Path("boot/__init__.py"))
    assert imports == ["__future__", "importlib"]
    source = Path("boot/__init__.py").read_text(encoding="utf-8")
    assert 'import_module("boot.public_api")' not in source
    assert 'runtime.bootstrap.runtime_builder' in source
    assert 'runtime.bootstrap.sovereign_bootstrap' in source
