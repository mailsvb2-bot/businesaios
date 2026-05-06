from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from ml.common.feature_vector import FeatureVector
from ml.common.score_output import ScoreOutput
from shared.numbers import coerce_float


@dataclass(frozen=True)
class BaseScoreModel:
    model_name: str
    default_base: float = 0.5
    default_confidence: float = 0.7
    feature_weights: Mapping[str, float] = field(default_factory=dict)

    def _number(self, value: object, default: float = 0.0) -> float:
        return coerce_float(value, default)

    def score(self, features: dict | None) -> ScoreOutput:
        raw_features = dict(features or {}) if isinstance(features, dict) else {}
        numeric_features = FeatureVector.from_mapping(raw_features).values
        score, reasons = self._score(numeric_features)
        bounded_score = max(0.0, min(1.0, self._number(score)))
        confidence = max(0.0, min(1.0, self._number(raw_features.get('confidence', self.default_confidence), self.default_confidence)))
        normalized_reasons = tuple(dict.fromkeys(str(item) for item in [self.model_name, *reasons] if str(item).strip()))
        return ScoreOutput(score=bounded_score, confidence=confidence, reasons=list(normalized_reasons))

    def _score(self, features: dict) -> tuple[float, list[str]]:
        base = self._number(features.get('base_score', self.default_base), self.default_base)
        weighted = sum(self._number(features.get(name, 0.0)) * self._number(weight, 0.0) for name, weight in self.feature_weights.items())
        penalty = max(0.0, self._number(features.get('penalty', 0.0), 0.0))
        return base + weighted - penalty, ['weighted_scoring']
