from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def _imports(relpath: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    tree = ast.parse(_read(relpath), filename=relpath)
    rows: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = "." * node.level + str(node.module or "")
            rows.append((module, tuple(alias.name for alias in node.names)))
    return tuple(rows)


def test_acquisition_boundary_modules_use_package_root() -> None:
    internal = {
        "acquisition/headless_entrypoint.py",
        "acquisition/request_adapter.py",
    }
    external = {
        "headless/acquisition_execution.py": "AcquisitionFeasibilityRequest",
        "presentation/acquisition_view_model.py": "AcquisitionFeasibilityResult",
        "advisory/acquisition_recommendation_builder.py": "AcquisitionFeasibilityResult",
        "advisory/acquisition_result_projection.py": "AcquisitionFeasibilityResult",
    }

    for relpath in internal:
        imports = _imports(relpath)
        assert any(module.startswith(".") for module, _ in imports), relpath
        assert not any(module.startswith("acquisition.") for module, _ in imports), relpath

    for relpath, symbol in external.items():
        imports = _imports(relpath)
        assert any(module == "acquisition" and symbol in names for module, names in imports), relpath
        assert not any(module.startswith("acquisition.") for module, _ in imports), relpath


def test_advisory_package_root_marks_owner_surface() -> None:
    content = _read("advisory/__init__.py")
    assert "CANON_ADVISORY_OWNER_SURFACE = True" in content
