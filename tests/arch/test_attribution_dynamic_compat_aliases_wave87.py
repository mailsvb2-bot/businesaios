from __future__ import annotations

import importlib
from pathlib import Path

import attribution as attribution_root
from attribution import ATTRIBUTION_COMPAT_EXPORTS, catalog


def test_attribution_root_is_thin_catalog_facade() -> None:
    assert attribution_root.CANON_ATTRIBUTION_COMPAT_SHIM is True
    text = Path(attribution_root.__spec__.origin).read_text(encoding="utf-8")
    assert "ATTRIBUTION_COMPAT_EXPORTS = _owner().ATTRIBUTION_COMPAT_EXPORTS" in text
    assert ".catalog import" not in text
    assert "sys.modules" not in text
    assert "types.ModuleType" not in text
    assert "_install_compat_aliases" not in text


def test_attribution_compat_modules_are_physical_pure_reexports() -> None:
    for export_name, module_name in ATTRIBUTION_COMPAT_EXPORTS.items():
        module = importlib.import_module(f"attribution.{module_name}")
        assert getattr(module, export_name) is getattr(catalog, export_name)
        assert module.__all__ == [export_name]
        path = Path(module.__file__)
        assert path.name == f"{module_name}.py"
        text = path.read_text(encoding="utf-8")
        assert f"from attribution.catalog import {export_name}" in text
        assert "class " not in text
        assert "def " not in text
        assert "__file__ =" not in text
