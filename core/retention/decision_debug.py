from __future__ import annotations

from typing import Any

from core.retention.constraints import constraints_from_retention_features


def build_retention_debug(decision: Any) -> dict[str, Any]:
    debug = dict(decision.debug or {}) if isinstance(getattr(decision, "debug", None), dict) else {}
    features = {
        "churn_risk": float(getattr(decision, "hazard", 0.0) or 0.0),
        "readiness": float(getattr(decision, "readiness", 0.0) or 0.0),
    }
    debug.setdefault("retention", {})
    debug["retention"].update(
        {
            "hazard": features["churn_risk"],
            "readiness": features["readiness"],
            "day_index": int(getattr(decision, "day_index", 0) or 0),
            "day_key": str(getattr(decision, "day_key", "") or ""),
        }
    )
    debug["features"] = dict(features)
    debug["price_constraints_override"] = constraints_from_retention_features(debug["features"])
    return debug
