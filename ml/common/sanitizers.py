from __future__ import annotations

from shared.numbers import coerce_float


def safe_feature_mapping(payload: dict | None) -> dict[str, float]:
    if not payload:
        return {}
    return {str(key): coerce_float(value, 0.0) for key, value in dict(payload).items()}
