from __future__ import annotations

from typing import Sequence

from core.product.types import FeatureRecord


class InMemoryFeatureReader:
    def __init__(self, features_by_product: dict[str, list[FeatureRecord]] | None = None) -> None:
        self._features_by_product = features_by_product or {}

    def read_features(self, product_id: str) -> Sequence[FeatureRecord]:
        return list(self._features_by_product.get(product_id, []))
