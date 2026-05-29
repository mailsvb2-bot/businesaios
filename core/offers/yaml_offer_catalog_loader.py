from __future__ import annotations

"""Compatibility adapter for raw YAML offer catalog specs.

Canonical parsing/validation/path-discipline live in:
    core.offers.catalogs.yaml_catalog_loader

This module stays only as a thin adapter for older callers that still expect
raw mapping specs instead of OfferCatalog objects.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.offers.catalogs.yaml_catalog_loader import (
    load_all_yaml_offer_catalog_specs,
    load_yaml_offer_catalog_spec,
)


@dataclass(frozen=True)
class YamlOfferCatalogLoader:
    """Thin compatibility shim returning raw spec mappings."""

    base_dir: Path

    def load_file(self, relpath: str) -> Mapping[str, Any]:
        return load_yaml_offer_catalog_spec(base_dir=self.base_dir, filename=relpath)

    def load_all(self) -> dict[str, Mapping[str, Any]]:
        return load_all_yaml_offer_catalog_specs(base_dir=self.base_dir)


# Backwards-compatible alias (older patches referenced V1 name).
YamlOfferCatalogLoaderV1 = YamlOfferCatalogLoader
