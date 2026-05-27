from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.contracts import BusinessExecutionRequest
from application.capability.capability_execution_verdict import CapabilityExecutionVerdictBuilder


@dataclass(frozen=True)
class BusinessAutonomyGovernanceAlignment:
    execution_verdict: Mapping[str, Any]
    normalized_request: Mapping[str, Any]


class BusinessAutonomyCapabilityVerdictBridge:
    """Advisory bridge into the canonical capability/autonomy governance semantics.

    This bridge must not create a second execution path. It only materializes the
    same platform governance semantics in a shape that business_autonomy can attach
    to audit/ops/admin surfaces.
    """

    def __init__(self, builder: CapabilityExecutionVerdictBuilder | None = None) -> None:
        self._builder = builder or CapabilityExecutionVerdictBuilder()

    def build_alignment(
        self,
        *,
        request: BusinessExecutionRequest,
        capability_allowed: bool,
        policy_verdict: Mapping[str, Any] | None = None,
    ) -> BusinessAutonomyGovernanceAlignment:
        adapted_request = _CapabilityVerdictRequest.from_business_request(request)
        payload = {
            "tenant_id": adapted_request.tenant_id,
            "estimated_cost": request.envelope.goal_payload.get("estimated_cost", 0.0),
            "outbound_count": request.envelope.goal_payload.get("outbound_count", 0),
            "approval_required": any(
                item.name == "require_human_approval" and bool(item.value) is True
                for item in request.envelope.constraints
            ),
            "persistent_counters": dict(request.envelope.metadata.get("persistent_counters") or {}),
            "capability_context": {
                "runtime": {
                    "enabled": capability_allowed,
                    "confidence_score": 1.0 if capability_allowed else 0.0,
                    "health_score": 1.0 if capability_allowed else 0.0,
                    "staleness_state": request.envelope.metadata.get("staleness_state", "fresh"),
                    "evidence_state": request.envelope.metadata.get("evidence_state", "verified"),
                }
            },
        }
        verdict = self._builder.build(
            request=adapted_request,
            action_type=request.envelope.goal_type,
            payload=payload,
            capability_allowed=capability_allowed,
            fallback_action_type=None,
            policy_verdict=policy_verdict,
        )
        return BusinessAutonomyGovernanceAlignment(
            execution_verdict=verdict.to_dict(),
            normalized_request={
                "tenant_id": adapted_request.tenant_id,
                "autonomy_tier": adapted_request.autonomy_tier,
                "approval_policy": dict(adapted_request.approval_policy),
                "constraints": dict(adapted_request.constraints),
            },
        )


class _CapabilityVerdictRequest:
    def __init__(
        self,
        *,
        tenant_id: str,
        autonomy_tier: str,
        approval_policy: Mapping[str, Any],
        constraints: Mapping[str, Any],
        meta: Mapping[str, Any],
    ) -> None:
        self.tenant_id = tenant_id
        self.autonomy_tier = autonomy_tier
        self.approval_policy = dict(approval_policy)
        self.constraints = dict(constraints)
        self.meta = dict(meta)

    @classmethod
    def from_business_request(cls, request: BusinessExecutionRequest) -> "_CapabilityVerdictRequest":
        tenant_id = str(request.envelope.metadata.get("tenant_id") or request.envelope.business_id or "global")
        approval_policy = dict(request.envelope.metadata.get("approval_policy") or {})
        constraints: dict[str, Any] = {}
        for item in request.envelope.constraints:
            constraints[item.name] = item.value
        if "max_outbound_per_window" not in constraints and "outbound_message_limit" in constraints:
            constraints["max_outbound_per_window"] = constraints["outbound_message_limit"]
        if "max_actions_per_day" not in constraints:
            constraints["max_actions_per_day"] = request.envelope.metadata.get("max_actions_per_day", 100)
        if "max_actions_per_hour" not in constraints:
            constraints["max_actions_per_hour"] = request.envelope.metadata.get("max_actions_per_hour", 25)
        autonomy_tier = str(request.envelope.metadata.get("autonomy_tier") or "bounded_autonomy")
        return cls(
            tenant_id=tenant_id,
            autonomy_tier=autonomy_tier,
            approval_policy=approval_policy,
            constraints=constraints,
            meta=dict(request.envelope.metadata),
        )


__all__ = [
    "BusinessAutonomyCapabilityVerdictBridge",
    "BusinessAutonomyGovernanceAlignment",
]
