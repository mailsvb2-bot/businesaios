from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.action_capability_matrix import get_action_capability
from execution.action_budget_engine import ActionBudgetEngine


CANON_HEADLESS_BLAST_RADIUS_GUARD = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


_TIER_DEFAULTS: dict[str, dict[str, float | int]] = {
    "advisory": {
        "blast_radius_max_actions_per_hour": 0,
        "blast_radius_max_actions_per_day": 0,
        "blast_radius_max_outbound_per_window": 0,
        "blast_radius_max_budget_change_per_window": 0.0,
        "blast_radius_max_new_pages_per_day": 0,
        "blast_radius_max_irreversible_actions_per_window": 0,
        "blast_radius_max_per_hour": 0,
    },
    "supervised": {
        "blast_radius_max_actions_per_hour": 5,
        "blast_radius_max_actions_per_day": 20,
        "blast_radius_max_outbound_per_window": 25,
        "blast_radius_max_budget_change_per_window": 25.0,
        "blast_radius_max_new_pages_per_day": 2,
        "blast_radius_max_irreversible_actions_per_window": 1,
        "blast_radius_max_per_hour": 5,
    },
    "bounded_autonomy": {
        "blast_radius_max_actions_per_hour": 10,
        "blast_radius_max_actions_per_day": 50,
        "blast_radius_max_outbound_per_window": 50,
        "blast_radius_max_budget_change_per_window": 50.0,
        "blast_radius_max_new_pages_per_day": 5,
        "blast_radius_max_irreversible_actions_per_window": 1,
        "blast_radius_max_per_hour": 10,
    },
    "full_autonomy": {
        "blast_radius_max_actions_per_hour": 25,
        "blast_radius_max_actions_per_day": 150,
        "blast_radius_max_outbound_per_window": 200,
        "blast_radius_max_budget_change_per_window": 250.0,
        "blast_radius_max_new_pages_per_day": 20,
        "blast_radius_max_irreversible_actions_per_window": 3,
        "blast_radius_max_per_hour": 25,
    },
}


@dataclass(frozen=True)
class BlastRadiusDecision:
    allowed: bool
    reason: str | None = None
    details: dict[str, Any] | None = None


class BlastRadiusGuard:
    def __init__(self, *, action_budget_engine: ActionBudgetEngine | None = None) -> None:
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()

    @staticmethod
    def _tier(value: object) -> str:
        text = str(value or "").strip()
        return text if text in _TIER_DEFAULTS else "supervised"

    @staticmethod
    def _resolve_limit(*, request: Any | None, autonomy_tier: str, name: str) -> float | int:
        defaults = _TIER_DEFAULTS.get(autonomy_tier, _TIER_DEFAULTS["supervised"])
        if request is not None:
            constraints = _safe_dict(getattr(request, "constraints", {}) or {})
            approval = _safe_dict(getattr(request, "approval_policy", {}) or {})
            blast = _safe_dict(approval.get("blast_radius") or {})
            if constraints.get(name) is not None:
                return constraints[name]
            # backward compatibility
            if name == "blast_radius_max_actions_per_hour" and constraints.get("blast_radius_max_per_hour") is not None:
                return constraints["blast_radius_max_per_hour"]
            if blast.get(name) is not None:
                return blast[name]
        return defaults[name]

    @staticmethod
    def _event_log_count(*, event_log: Any | None, tenant_id: str, action_type: str, period: str) -> int:
        if event_log is None:
            return 0
        count_recent = getattr(event_log, "count_recent", None)
        if callable(count_recent):
            try:
                return max(0, int(count_recent(tenant_id=str(tenant_id), action=str(action_type), period=str(period))))
            except Exception:
                return 0
        query_recent = getattr(event_log, "query_recent", None)
        if callable(query_recent):
            try:
                rows = query_recent(event_type="decision_executed", since_ms=0, filters={"tenant_id": str(tenant_id), "action": str(action_type), "period": str(period)})
                return len(list(rows or []))
            except Exception:
                return 0
        return 0

    def evaluate(
        self,
        *,
        request: Any | None,
        action: Any | None = None,
        action_type: str = "",
        payload: Mapping[str, Any] | None = None,
        event_log: Any | None = None,
        tenant_id: str | None = None,
        autonomy_tier: str | None = None,
        recent_actions: list[dict[str, Any]] | None = None,
    ) -> BlastRadiusDecision:
        resolved_action_type = str(action_type or getattr(action, "action_type", "") or getattr(action, "action", "") or "")
        capability = get_action_capability(resolved_action_type)
        if not capability.bounded_by_blast_radius:
            return BlastRadiusDecision(allowed=True, reason="not_bounded")

        resolved_tenant_id = str(tenant_id or getattr(request, "tenant_id", "default") or "default")
        resolved_tier = self._tier(autonomy_tier or getattr(request, "autonomy_tier", "supervised") or "supervised")
        recent = _safe_list(recent_actions)
        effective_payload = _safe_dict(payload if payload is not None else getattr(action, "payload", {}) or {})
        cost = self._action_budget_engine.estimate_cost(action_type=resolved_action_type, payload=effective_payload)

        persistent_counters = _safe_dict(effective_payload.get("persistent_counters") or {})
        current_actions_hour = max(len(recent), _safe_int(persistent_counters.get("actions_hour"))) + self._event_log_count(event_log=event_log, tenant_id=resolved_tenant_id, action_type=resolved_action_type, period="hour")
        current_actions_day = max(len(recent), _safe_int(persistent_counters.get("actions_day"))) + self._event_log_count(event_log=event_log, tenant_id=resolved_tenant_id, action_type=resolved_action_type, period="day")
        current_outbound = max(sum(max(0, _safe_int(_safe_dict(item).get("outbound_count"))) for item in recent), _safe_int(persistent_counters.get("outbound_total")))
        current_budget_change = max(sum(max(0.0, _safe_float(_safe_dict(item).get("budget_change_amount"))) for item in recent), _safe_float(persistent_counters.get("budget_change_total")))
        current_publications = max(sum(max(0, _safe_int(_safe_dict(item).get("publication_count"))) for item in recent), _safe_int(persistent_counters.get("publication_total")))
        current_irreversible = max(sum(max(0, _safe_int(_safe_dict(item).get("irreversible_count"))) for item in recent), _safe_int(persistent_counters.get("irreversible_total")))

        proposed = {
            "actions_hour": int(current_actions_hour + 1),
            "actions_day": int(current_actions_day + 1),
            "outbound": int(current_outbound + cost.outbound_count),
            "budget_change": float(current_budget_change + cost.budget_change_amount),
            "new_pages": int(current_publications + cost.publication_count),
            "irreversible": int(current_irreversible + cost.irreversible_count),
        }
        limits = {
            "blast_radius_max_actions_per_hour": max(0, _safe_int(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_actions_per_hour"))),
            "blast_radius_max_actions_per_day": max(0, _safe_int(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_actions_per_day"))),
            "blast_radius_max_outbound_per_window": max(0, _safe_int(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_outbound_per_window"))),
            "blast_radius_max_budget_change_per_window": max(0.0, _safe_float(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_budget_change_per_window"))),
            "blast_radius_max_new_pages_per_day": max(0, _safe_int(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_new_pages_per_day"))),
            "blast_radius_max_irreversible_actions_per_window": max(0, _safe_int(self._resolve_limit(request=request, autonomy_tier=resolved_tier, name="blast_radius_max_irreversible_actions_per_window"))),
        }

        violations: list[str] = []
        if limits["blast_radius_max_actions_per_hour"] > 0 and proposed["actions_hour"] > limits["blast_radius_max_actions_per_hour"]:
            violations.append("blast_radius_max_actions_per_hour")
        if limits["blast_radius_max_actions_per_day"] > 0 and proposed["actions_day"] > limits["blast_radius_max_actions_per_day"]:
            violations.append("blast_radius_max_actions_per_day")
        if limits["blast_radius_max_outbound_per_window"] > 0 and proposed["outbound"] > limits["blast_radius_max_outbound_per_window"]:
            violations.append("blast_radius_max_outbound_per_window")
        if limits["blast_radius_max_budget_change_per_window"] > 0.0 and proposed["budget_change"] > limits["blast_radius_max_budget_change_per_window"]:
            violations.append("blast_radius_max_budget_change_per_window")
        if limits["blast_radius_max_new_pages_per_day"] > 0 and proposed["new_pages"] > limits["blast_radius_max_new_pages_per_day"]:
            violations.append("blast_radius_max_new_pages_per_day")
        if limits["blast_radius_max_irreversible_actions_per_window"] > 0 and proposed["irreversible"] > limits["blast_radius_max_irreversible_actions_per_window"]:
            violations.append("blast_radius_max_irreversible_actions_per_window")

        if violations:
            return BlastRadiusDecision(
                allowed=False,
                reason="blast_radius_exceeded",
                details={
                    "action_type": resolved_action_type,
                    "tenant_id": resolved_tenant_id,
                    "autonomy_tier": resolved_tier,
                    "violated_limits": violations,
                    "limits": limits,
                    "proposed": proposed,
                    "recent_actions_count": len(recent),
                },
            )
        return BlastRadiusDecision(
            allowed=True,
            reason="within_blast_radius",
            details={
                "action_type": resolved_action_type,
                "tenant_id": resolved_tenant_id,
                "autonomy_tier": resolved_tier,
                "limits": limits,
                "proposed": proposed,
            },
        )


__all__ = [
    "CANON_HEADLESS_BLAST_RADIUS_GUARD",
    "BlastRadiusDecision",
    "BlastRadiusGuard",
]
