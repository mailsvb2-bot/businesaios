from __future__ import annotations

from pathlib import Path

from core.behavior.operator_policy_catalogs.loader import OperatorPolicyCatalogLoader
from core.behavior.operator_policy_catalogs.models import OperatorPolicyCatalog


class OperatorPolicyCatalogRegistry:
    def __init__(self, root: Path) -> None:
        self._loader = OperatorPolicyCatalogLoader(root)
        self._cache: dict[str, OperatorPolicyCatalog | None] = {}

    def get(self, catalog_ref: str) -> OperatorPolicyCatalog | None:
        if catalog_ref not in self._cache:
            self._cache[catalog_ref] = self._loader.load(catalog_ref)
        return self._cache[catalog_ref]
