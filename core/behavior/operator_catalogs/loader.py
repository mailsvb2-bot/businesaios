from __future__ import annotations

from pathlib import Path
from typing import Any

from core.behavior.operator_catalogs.defaults import DEFAULT_OPERATOR_CATALOG
from core.behavior.operator_catalogs.models import OperatorCatalog
from core.behavior.operator_catalogs.parser import parse_operator_catalog

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class OperatorCatalogLoader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, catalog_ref: str) -> OperatorCatalog:
        if yaml is None:
            return DEFAULT_OPERATOR_CATALOG
        path = self._root / f"{catalog_ref}.yaml"
        if not path.exists():
            return DEFAULT_OPERATOR_CATALOG
        payload: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return DEFAULT_OPERATOR_CATALOG
        return parse_operator_catalog(payload)
