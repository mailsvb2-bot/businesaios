from __future__ import annotations

from core.product.types import FeatureScore


class InMemoryFeatureWriter:
    def __init__(self) -> None:
        self._scores_by_product: dict[str, list[FeatureScore]] = {}

    def write_feature_score(self, product_id: str, score: FeatureScore) -> None:
        self._scores_by_product.setdefault(product_id, []).append(score)

    def list_scores(self, product_id: str) -> list[FeatureScore]:
        return list(self._scores_by_product.get(product_id, []))
