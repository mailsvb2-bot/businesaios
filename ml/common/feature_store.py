from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Mapping
from ml.common.feature_vector import FeatureVector


@dataclass
class FeatureStore:
    features: Dict[str, FeatureVector] = field(default_factory=dict)

    def put(self, entity_id: str, values: Mapping[str, object]) -> None:
        normalized = str(entity_id or '').strip()
        if not normalized:
            raise ValueError('entity_id must be non-empty')
        if not isinstance(values, Mapping):
            raise ValueError('feature values must be a mapping')
        self.features[normalized] = FeatureVector.from_mapping(values)

    def has(self, entity_id: str) -> bool:
        normalized = str(entity_id or '').strip()
        if not normalized:
            raise ValueError('entity_id must be non-empty')
        return normalized in self.features

    def get(self, entity_id: str) -> FeatureVector:
        normalized = str(entity_id or '').strip()
        if not normalized:
            raise ValueError('entity_id must be non-empty')
        return self.features.get(normalized, FeatureVector())

    def require(self, entity_id: str) -> FeatureVector:
        normalized = str(entity_id or '').strip()
        if not normalized:
            raise ValueError('entity_id must be non-empty')
        if normalized not in self.features:
            raise KeyError(normalized)
        return self.features[normalized]
