from __future__ import annotations

from dataclasses import dataclass

from application.autonomy.autonomy_tiers import evaluate_autonomy_tier
from application.business_autonomy.contracts import BusinessExecutionRequest, CapabilityKind, IntegrationMode
from application.business_autonomy.policy_semantics_guard import PolicySemanticsGuard
from application.business_autonomy.registry import BusinessCapabilityRegistry
from application.business_autonomy.trust import BusinessTrustRegistry, BusinessTrustTier, TrustPolicyDecision


@dataclass(frozen=True)
class AutonomyPolicyDecision:
    allowed: bool
    mode: IntegrationMode
    reason: str


class BusinessAutonomyPolicy:
    """
    Canon:
    - headless is the internal canonical execution path of the platform;
    - business_autonomy is an external boundary owner for connected businesses;
    - capability/autonomy/planning semantics stay in shared platform layers;
    - business_autonomy may normalize and consume these semantics, but must not duplicate them.
    """

    def __init__(self, capability_registry: BusinessCapabilityRegistry) -> None:
        self._capability_registry = capability_registry
        self._semantics_guard = PolicySemanticsGuard()

    def choose_mode(self, request: BusinessExecutionRequest) -> AutonomyPolicyDecision:
        if request.envelope.simulation:
            return AutonomyPolicyDecision(True, IntegrationMode.OBSERVE_ONLY, "Simulation uses observe-only path.")
        if _has_hard_stop_constraint(request):
            return AutonomyPolicyDecision(False, request.integration_mode, "Request blocked by hard policy constraint.")

        semantics = self._semantics_guard.normalize(dict(request.envelope.metadata or {}))
        action_type = str(request.envelope.metadata.get("action_type") or request.envelope.goal_type or "")
        autonomy = evaluate_autonomy_tier(
            action_type=action_type,
            autonomy_tier=semantics.autonomy_tier,
            approval_policy={
                **dict(semantics.approval_policy),
                "capability_matrix": dict(semantics.capability_policy),
            },
        )
        if autonomy.blocked_by_policy:
            return AutonomyPolicyDecision(False, request.integration_mode, autonomy.handoff_reason or "Blocked by autonomy policy.")

        business_id = request.envelope.business_id
        has_domain_owner = any(
            self._capability_registry.supports(business_id, kind)
            for kind in (
                CapabilityKind.DOMAIN_AI,
                CapabilityKind.DOMAIN_PLANNER,
                CapabilityKind.DOMAIN_SCHEDULER,
            )
        )
        non_ai_mode = str(request.envelope.metadata.get("non_ai_mode") or "").strip().lower()
        if has_domain_owner:
            return AutonomyPolicyDecision(
                allowed=not autonomy.blocked_by_policy,
                mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
                reason="Business declares domain-owner capabilities; delegated adapter path is canonical.",
            )
        if non_ai_mode == "low_autonomy":
            return AutonomyPolicyDecision(True, IntegrationMode.LOW_AUTONOMY, "Non-AI business uses low-autonomy adapter path.")
        if autonomy.approval_required or non_ai_mode in {"supervised", "external_human_owned"}:
            return AutonomyPolicyDecision(True, IntegrationMode.SUPERVISED, autonomy.handoff_reason or "Supervised adapter path selected.")
        return AutonomyPolicyDecision(
            True,
            IntegrationMode.PLATFORM_DIRECT,
            "Business has no domain-owner capabilities; platform-direct path allowed.",
        )


def _has_hard_stop_constraint(request: BusinessExecutionRequest) -> bool:
    return any(
        item.name == "execution_forbidden" and bool(item.value) is True and item.severity.value == "hard"
        for item in request.envelope.constraints
    )


class BusinessTrustPolicy:
    def __init__(self, trust_registry: BusinessTrustRegistry) -> None:
        self._trust_registry = trust_registry

    def evaluate(self, request: BusinessExecutionRequest) -> TrustPolicyDecision:
        snapshot = self._trust_registry.get(request.envelope.business_id)
        if snapshot.trust_tier in {BusinessTrustTier.CRITICAL, BusinessTrustTier.HIGH}:
            return TrustPolicyDecision(True, False, "Trust tier allows delegated execution.")
        if snapshot.trust_tier == BusinessTrustTier.MEDIUM:
            requires = bool(request.envelope.priority >= 80)
            return TrustPolicyDecision(True, requires, "Medium trust requires approval for higher-risk requests.")
        if snapshot.trust_tier == BusinessTrustTier.LOW:
            return TrustPolicyDecision(True, True, "Low trust requires explicit operator approval.")
        return TrustPolicyDecision(False, False, "Unknown trust tier blocks delegated execution.")
