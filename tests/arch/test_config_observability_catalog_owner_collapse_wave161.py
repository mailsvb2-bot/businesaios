from __future__ import annotations

from pathlib import Path


def test_config_package_root_no_direct_catalog_import() -> None:
    text = Path("config/__init__.py").read_text(encoding="utf-8")
    assert "from config.catalog import" not in text
    assert "import_module('config.catalog')" in text
    assert "CANON_CONFIG_PACKAGE_OWNER" in text


def test_observability_package_root_no_direct_catalog_import() -> None:
    text = Path("observability/__init__.py").read_text(encoding="utf-8")
    assert "from observability.catalog import" not in text
    assert "import_module('observability.catalog')" in text
    assert "CANON_OBSERVABILITY_PACKAGE_OWNER" in text
