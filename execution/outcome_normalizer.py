from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
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

        for key in (
            "margin",
            "margin_amount",
            "net_margin",
            "gross_margin",
            "conversion_rate",
            "retention_rate",
            "actual_cost",
            "cost",
            "spend",
            "latency_ms",
            "execution_latency_ms",
            "latency_seconds",
            "complaint_count",
            "complaints",
            "policy_violation_count",
            "policy_violations",
            "execution_failure_count",
            "execution_failures",
        ):
            if key not in data:
                continue
            value = self._to_optional_float(data.get(key))
            if value is not None:
                normalized[key] = value

        observed_boolean_fields = {
            "retained": "retention_observed",
            "retention_success": "retention_observed",
            "complaint": "complaint_observed",
            "human_override": "human_override_observed",
            "override_applied": "human_override_observed",
            "operator_override": "human_override_observed",
            "policy_violation": "policy_violation_observed",
            "execution_failure": "execution_failure_observed",
        }
        for key, marker in observed_boolean_fields.items():
            if key not in data:
                continue
            value = self._to_optional_bool(data.get(key))
            if value is not None:
                normalized[key] = value
                normalized[marker] = True

        if "revenue" in data:
            normalized["revenue_observed"] = True
        if "converted" in data or "conversion_rate" in data:
            normalized["conversion_observed"] = True
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

    @staticmethod
    def _to_optional_float(value: Any) -> float | None:
        if isinstance(value, bool) or value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if isfinite(number) else None

    @staticmethod
    def _to_optional_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "ok"}:
                return True
            if normalized in {"0", "false", "no"}:
                return False
        return None

__all__ = ["CANON_HEADLESS_OUTCOME_NORMALIZER", "OutcomeNormalizer"]
