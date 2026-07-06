from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def constraints_from_retention_features(features: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic translation from retention signals to price constraints.

    Higher churn risk lowers the allowed pricing band.
    Returned mapping is merged into WorldState price constraints.
    """
    try:
        churn = float(features.get("churn_risk", 0.0) or 0.0)
    except Exception:
        churn = 0.0

    if churn >= 0.75:
        return {"max_band": "low"}
    if churn >= 0.45:
        return {"max_band": "standard"}
    return {}
