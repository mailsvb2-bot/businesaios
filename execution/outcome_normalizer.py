from __future__ import annotations
from dataclasses import dataclass
from typing import Any

CANON_HEADLESS_OUTCOME_NORMALIZER = True

@dataclass(frozen=True)
class OutcomeNormalizer:
    """Normalize heterogeneous action outputs into a stable outcome schema."""

    def normalize(self, *, output: Any, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if isinstance(payload, dict):
            if isinstance(payload.get("feedback_seed"), dict):
                data.update(dict(payload["feedback_seed"]))
            if "terminal" in payload:
                data.setdefault("terminal", payload.get("terminal"))
        if isinstance(output, dict):
            data.update(output)
        converted = self._to_bool(data.get("converted"))
        normalized = {
            "revenue": self._to_float(data.get("revenue")),
            "converted": converted,
            "responded": self._to_bool(data.get("responded")),
            "terminal": self._to_bool(data.get("terminal")),
            "customer_success": self._to_bool(data.get("customer_success")) or converted,
            "goal_reached": self._to_bool(data.get("goal_reached")),
        }
        for key in ("lead_count", "client_count", "churn_reduced", "retained_users", "funnel_started", "message_sent", "observed_progress_score"):
            if key in data:
                normalized[key] = data[key]
        return normalized

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return value.strip().lower() in {"1", "true", "yes", "ok"} if isinstance(value, str) else False

__all__ = ["CANON_HEADLESS_OUTCOME_NORMALIZER", "OutcomeNormalizer"]
