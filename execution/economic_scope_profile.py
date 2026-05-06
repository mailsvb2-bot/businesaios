from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_SCOPE_PROFILE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(0, int(parsed))


@dataclass(frozen=True, slots=True)
class EconomicScopeProfile:
    tenant_id: str
    business_id: str
    tenant_tier: str
    business_tier: str
    profile_name: str
    retention_policy: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "tenant_tier": self.tenant_tier,
            "business_tier": self.business_tier,
            "profile_name": self.profile_name,
            "retention_policy": dict(self.retention_policy),
            "metadata": dict(self.metadata),
        }


class EconomicScopeProfileResolver:
    """
    Read-only retention/export profile resolver.

    Important:
    - Does not decide actions.
    - Does not compute economic policy.
    - Only resolves canonical scope-aware retention/export settings.
    """

    def __init__(self, *, base_retention_policy: Mapping[str, Any] | None = None) -> None:
        self._base_retention_policy = _safe_dict(base_retention_policy)

    def resolve(
        self,
        *,
        action: Mapping[str, Any] | None,
        execution_receipt: Mapping[str, Any] | None,
        economic_policy: Mapping[str, Any] | None = None,
    ) -> EconomicScopeProfile:
        action_payload = _safe_dict(action)
        receipt_payload = _safe_dict(execution_receipt)
        economic_payload = _safe_dict(economic_policy)
        base = dict(self._base_retention_policy)

        tenant_id = _text(action_payload.get("tenant_id") or receipt_payload.get("tenant_id"), default="default")
        business_id = _text(action_payload.get("business_id") or receipt_payload.get("business_id"), default="default")
        tenant_tier = _text(
            action_payload.get("tenant_tier")
            or receipt_payload.get("tenant_tier")
            or _safe_dict(action_payload.get("tenant_scope")).get("tenant_tier"),
            default="standard",
        )
        business_tier = _text(
            action_payload.get("business_tier")
            or receipt_payload.get("business_tier")
            or _safe_dict(action_payload.get("tenant_scope")).get("business_tier"),
            default="standard",
        )
        survival_mode = _text(economic_payload.get("survival_mode"), default="normal")
        operator_required = bool(economic_payload.get("operator_required"))

        profile_name = self._profile_name(
            tenant_tier=tenant_tier,
            business_tier=business_tier,
            survival_mode=survival_mode,
            operator_required=operator_required,
        )
        retention_policy = self._retention_for_profile(base=base, profile_name=profile_name)
        retention_policy.setdefault("metadata", {})
        retention_policy["metadata"] = {
            **_safe_dict(retention_policy.get("metadata")),
            "owner": "execution.economic_scope_profile",
            "profile_name": profile_name,
            "tenant_id": tenant_id,
            "business_id": business_id,
            "tenant_tier": tenant_tier,
            "business_tier": business_tier,
        }
        return EconomicScopeProfile(
            tenant_id=tenant_id,
            business_id=business_id,
            tenant_tier=tenant_tier,
            business_tier=business_tier,
            profile_name=profile_name,
            retention_policy=retention_policy,
            metadata={
                "owner": "execution.economic_scope_profile",
                "survival_mode": survival_mode,
                "operator_required": operator_required,
            },
        )

    @staticmethod
    def _profile_name(*, tenant_tier: str, business_tier: str, survival_mode: str, operator_required: bool) -> str:
        normalized_tenant = tenant_tier.casefold()
        normalized_business = business_tier.casefold()
        if survival_mode == "survival" or operator_required:
            return "guarded"
        if normalized_tenant in {"enterprise", "critical", "regulated"} or normalized_business in {"enterprise", "critical", "regulated"}:
            return "regulated"
        if normalized_tenant in {"premium", "pro"} or normalized_business in {"premium", "pro"}:
            return "extended"
        return "standard"

    @staticmethod
    def _retention_for_profile(*, base: dict[str, Any], profile_name: str) -> dict[str, Any]:
        policy = dict(base)
        profiles = {
            "standard": {
                "max_feedback_rows": 250,
                "max_roi_rows": 250,
                "max_snapshot_rows": 250,
                "max_trace_rows": 250,
                "max_metrics_rows": 250,
                "max_age_days": 30,
                "max_snapshot_age_days": 60,
            },
            "extended": {
                "max_feedback_rows": 500,
                "max_roi_rows": 500,
                "max_snapshot_rows": 500,
                "max_trace_rows": 500,
                "max_metrics_rows": 500,
                "max_age_days": 60,
                "max_snapshot_age_days": 90,
                "max_trace_age_days": 90,
            },
            "regulated": {
                "max_feedback_rows": 1000,
                "max_roi_rows": 1000,
                "max_snapshot_rows": 1200,
                "max_trace_rows": 1200,
                "max_metrics_rows": 1000,
                "max_age_days": 180,
                "max_snapshot_age_days": 365,
                "max_trace_age_days": 365,
                "max_metrics_age_days": 180,
            },
            "guarded": {
                "max_feedback_rows": 150,
                "max_roi_rows": 150,
                "max_snapshot_rows": 300,
                "max_trace_rows": 300,
                "max_metrics_rows": 200,
                "max_age_days": 21,
                "max_snapshot_age_days": 90,
                "max_trace_age_days": 90,
            },
        }
        selected = profiles.get(profile_name, profiles["standard"])
        merged = {**selected, **policy}
        return merged


__all__ = [
    "CANON_ECONOMIC_SCOPE_PROFILE",
    "EconomicScopeProfile",
    "EconomicScopeProfileResolver",
]
