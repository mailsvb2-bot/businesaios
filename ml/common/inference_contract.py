from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict

from shared.numbers import coerce_float


@dataclass(frozen=True)
class InferenceContract:
    model_name: str
    entity_id: str
    features: Dict[str, float] = field(default_factory=dict)
    context: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not str(self.model_name).strip():
            issues.append('missing_model_name')
        if not str(self.entity_id).strip():
            issues.append('missing_entity_id')
        if not isinstance(self.features, dict):
            return issues + ['features_must_be_dict']
        if not isinstance(self.context, dict):
            issues.append('context_must_be_dict')
        for name, value in self.features.items():
            if not str(name).strip():
                issues.append('empty_feature_key')
                continue
            if not isinstance(value, (int, float)):
                normalized = coerce_float(value, float('nan'))
                if normalized != normalized:
                    issues.append(f'non_numeric_feature:{name}')
                    continue
                value = normalized
            numeric = float(value)
            if not math.isfinite(numeric):
                issues.append(f'non_finite_feature:{name}')
        for key, value in dict(self.context).items() if isinstance(self.context, dict) else ():
            if not str(key).strip():
                issues.append('empty_context_key')
            if not isinstance(value, str):
                issues.append(f'non_string_context:{key}')
        return issues
