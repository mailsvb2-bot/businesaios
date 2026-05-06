from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
import math
import shared.types as _shared_types


@dataclass(frozen=True)
class DecisionCandidate:
    action_type: str
    channel: str
    score: float
    expected_value: float
    confidence: float
    reasons: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    candidate_id: str = field(default_factory=lambda: _shared_types.new_id('cand'))

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.action_type.strip() != self.action_type or not self.action_type:
            issues.append('invalid_action_type')
        if self.channel.strip() != self.channel or not self.channel:
            issues.append('invalid_channel')
        if not math.isfinite(float(self.score)) or self.score < 0.0:
            issues.append('invalid_score')
        if not math.isfinite(float(self.expected_value)) or self.expected_value < 0.0:
            issues.append('negative_expected_value')
        if not 0.0 <= self.confidence <= 1.0:
            issues.append('invalid_confidence')
        return issues

    def normalized_payload(self) -> Dict[str, Any]:
        return _shared_types.frozen_dict(self.payload)

    def objective_score(self, risk_penalty_weight: float = 1.0, confidence_penalty_weight: float = 0.5) -> float:
        risk = float(self.payload.get('risk_score', 0.0))
        confidence_gap = max(0.0, 1.0 - self.confidence)
        return float(self.expected_value + self.score - (risk * risk_penalty_weight) - (confidence_gap * confidence_penalty_weight))
