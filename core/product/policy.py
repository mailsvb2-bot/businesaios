from __future__ import annotations
from .contracts import ProductFeature

def is_feature_candidate(feature: ProductFeature, minimum: float = 0.1) -> bool:
    return feature.impact_score >= minimum
