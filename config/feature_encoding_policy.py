from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class FeatureEncodingPolicy:
    categorical_limit: int = 32
    numeric_fallback: float = 0.0
    intercept_value: float = 1.0
    true_value: float = 1.0
    false_value: float = 0.0
    one_hot_match_value: float = 1.0
    one_hot_miss_value: float = 0.0


DEFAULT_FEATURE_ENCODING_POLICY = FeatureEncodingPolicy()
