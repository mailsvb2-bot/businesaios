from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping


CANON_ECONOMIC_POLICY_SNAPSHOT = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True, slots=True)
class EconomicPolicySnapshot:
    snapshot_id: str
    action_type: str
    channel: str
    allowed: bool
    operator_required: bool
    reason: str
    survival_mode: str
    requested_budget: float
    approved_budget: float
    expected_roi: float
    risk_level: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "action_type": self.action_type,
            "channel": self.channel,
            "allowed": bool(self.allowed),
            "operator_required": bool(self.operator_required),
            "reason": self.reason,
            "survival_mode": self.survival_mode,
            "requested_budget": float(self.requested_budget),
            "approved_budget": float(self.approved_budget),
            "expected_roi": float(self.expected_roi),
            "risk_level": self.risk_level,
            "metadata": dict(self.metadata),
        }


class EconomicPolicySnapshotBuilder:
    """
    Canonical audit snapshot builder.

    Important:
    - Does not decide.
    - Does not recompute policy.
    - Only captures the outputs of the canonical economic path for replay/audit.
    """

    def build(
        self,
        *,
        snapshot_id: str,
        budget_guard_result: Mapping[str, Any] | None,
    ) -> EconomicPolicySnapshot:
        payload = _safe_dict(budget_guard_result)
        metadata = _safe_dict(payload.get("metadata"))
        signals = _safe_dict(metadata.get("planning_signals"))
        spend_limits = _safe_dict(payload.get("spend_limits"))
        risk_envelope = _safe_dict(metadata.get("risk_envelope"))
        economic_policy = _safe_dict(payload.get("economic_policy"))
        return EconomicPolicySnapshot(
            snapshot_id=_text(snapshot_id),
            action_type=_text(metadata.get("action_type") or signals.get("action_type") or "unknown"),
            channel=_text(metadata.get("channel") or signals.get("channel") or "default"),
            allowed=_safe_bool(payload.get("allowed")),
            operator_required=_safe_bool(payload.get("operator_required")),
            reason=_text(payload.get("reason") or economic_policy.get("reason") or ""),
            survival_mode=_text(signals.get("survival_mode") or economic_policy.get("survival_mode") or "normal"),
            requested_budget=_safe_float(signals.get("requested_budget"), default=_safe_float(spend_limits.get("requested_budget"))),
            approved_budget=_safe_float(signals.get("approved_budget"), default=_safe_float(spend_limits.get("approved_budget"))),
            expected_roi=_safe_float(signals.get("expected_roi"), default=_safe_float(_safe_dict(spend_limits.get("assessment")).get("expected_roi"))),
            risk_level=_text(risk_envelope.get("risk_level") or "low"),
            metadata={
                "owner": "execution.economic_policy_snapshot",
                "signal_source": _safe_dict(signals.get("metadata")).get("source"),
            },
        )


__all__ = [
    "CANON_ECONOMIC_POLICY_SNAPSHOT",
    "EconomicPolicySnapshot",
    "EconomicPolicySnapshotBuilder",
]
