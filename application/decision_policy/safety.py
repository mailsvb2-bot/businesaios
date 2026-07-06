from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from config.env_flags import env_int
from core.safety.blast_radius import BlastRadiusPolicy, allow_action
from runtime.safety_controls import evaluate_runtime_action_controls, first_blocking_decision, record_allowed_action


@dataclass(frozen=True)
class DecisionSafetyConfig:
    high_impact_rollout_pct: int
    blast_radius_max_per_hour: int

    @staticmethod
    def from_env() -> DecisionSafetyConfig:
        return DecisionSafetyConfig(
            high_impact_rollout_pct=env_int("AI_CEO_HIGH_IMPACT_ROLLOUT_PCT", 0, lo=0, hi=100),
            blast_radius_max_per_hour=env_int("AI_CEO_BLAST_RADIUS_MAX_PER_HOUR", 0, lo=0),
        )


_HIGH_IMPACT_PREFIXES = ("ads_apply_", "capture_payment", "apply_pricing_change")


def _percent_bucket(key: str) -> int:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    return int(h, 16) % 100


def _rollout_enabled(*, feature_key: str, tenant_id: str, user_id: str, percent: int) -> bool:
    p = int(percent or 0)
    if p <= 0:
        return False
    if p >= 100:
        return True
    bucket = _percent_bucket(f"{feature_key}|{tenant_id}|{user_id}")
    return bucket < p


def _legacy_high_impact_gate(*, action: str, tenant_id: str, user_id: str, event_log: Any) -> tuple[bool, str, dict[str, Any]]:
    cfg = DecisionSafetyConfig.from_env()
    is_high = str(action or "").startswith(_HIGH_IMPACT_PREFIXES)
    if is_high and not _rollout_enabled(
        feature_key="ai_ceo_high_impact",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        percent=int(cfg.high_impact_rollout_pct or 0),
    ):
        return False, "rollout_disabled", {"rollout_pct": int(cfg.high_impact_rollout_pct or 0)}

    ok, dbg = allow_action(
        policy=BlastRadiusPolicy(max_per_hour=int(cfg.blast_radius_max_per_hour or 0)),
        event_log=event_log,
        tenant_id=str(tenant_id),
        action=str(action or ""),
    )
    if not ok:
        return False, "blast_radius", dict(dbg)
    return True, "ok", {"high_impact": bool(is_high), **dict(dbg)}


def gate_decision_action(*, action: str, payload: dict[str, Any], tenant_id: str, user_id: str, event_log: Any) -> tuple[bool, str, dict[str, Any]]:
    data = dict(payload or {})
    data.setdefault("tenant_id", str(tenant_id))
    data.setdefault("user_id", str(user_id))

    control_decisions = evaluate_runtime_action_controls(action=action, payload=data)
    blocking = first_blocking_decision(control_decisions)
    if blocking is not None:
        return False, str(blocking.reason), {
            "control": str(blocking.control),
            "details": dict(blocking.details),
            "control_results": [
                {"control": d.control, "status": d.status.value, "reason": d.reason, "details": dict(d.details)}
                for d in control_decisions
            ],
        }

    ok, reason, debug = _legacy_high_impact_gate(
        action=action,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        event_log=event_log,
    )
    if not ok:
        return False, reason, debug

    record_allowed_action(action=action, payload=data)
    return True, "ok", {
        **dict(debug),
        "control_results": [
            {"control": d.control, "status": d.status.value, "reason": d.reason, "details": dict(d.details)}
            for d in control_decisions
        ],
    }
