from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from governance.economic.action_economics_model import ActionEconomicsIntent, ActionEconomicsSnapshot, EconomicPolicyVerdict, build_assessment
from governance.economic.capital_guard import CapitalGuard
from governance.economic.economic_policy_contract import EconomicPolicyConfig, EconomicReviewState, PolicyCheckResult
from governance.economic.margin_policy import MarginPolicy
from governance.economic.portfolio_budget_allocator import PortfolioBudgetAllocator
from governance.economic.spend_cap_policy import SpendCapPolicy
from governance.economic.stop_loss_policy import StopLossPolicy
from governance.economic.survival_mode_switch import SurvivalModeSwitch
from governance.economic.inference_roi_guard import InferenceROIGuard
from governance.economic.inference_runway_guard import InferenceRunwayGuard
from execution.inference_policy_guard import InferencePolicyEnvelope, InferencePolicyGuard

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class EconomicPolicyEngine:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def review(self, decision: Any, world_state: Any) -> EconomicPolicyVerdict:
        intent = ActionEconomicsIntent.from_decision(decision, config=self.config)
        snapshot = ActionEconomicsSnapshot.from_sources(decision=decision, world_state=world_state, config=self.config)
        assessment = build_assessment(intent, snapshot)

        capital_guard = CapitalGuard(config=self.config)
        margin_policy = MarginPolicy(config=self.config)
        spend_cap_policy = SpendCapPolicy(config=self.config)
        stop_loss_policy = StopLossPolicy(config=self.config)
        survival_mode_switch = SurvivalModeSwitch(config=self.config)
        portfolio_budget_allocator = PortfolioBudgetAllocator(config=self.config)

        checks: list[PolicyCheckResult] = []
        checks.extend(capital_guard.evaluate(assessment=assessment, snapshot=snapshot))
        checks.append(spend_cap_policy.evaluate(intent=intent, snapshot=snapshot, assessment=assessment))
        checks.append(margin_policy.evaluate(intent=intent, assessment=assessment, snapshot=snapshot))
        checks.append(stop_loss_policy.evaluate(intent=intent, assessment=assessment, snapshot=snapshot))

        unique_checks = self._dedupe_checks(checks)
        review_state = EconomicReviewState.from_checks(unique_checks)
        survival = survival_mode_switch.evaluate(assessment=assessment, snapshot=snapshot)
        portfolio = portfolio_budget_allocator.allocate(snapshot=snapshot, intent=intent)
        approved_budget = self._approved_budget(unique_checks=unique_checks, assessment=assessment)
        inference_policy = self._inference_capacity_policy(decision=decision, assessment=assessment)

        return EconomicPolicyVerdict(
            allowed=review_state.allowed,
            operator_required=review_state.operator_required,
            reason=review_state.primary_reason,
            reasons=review_state.veto_reasons + review_state.review_reasons,
            checks=unique_checks,
            survival_mode=survival.mode,
            assessment=assessment,
            portfolio_allocation=portfolio,
            metadata={
                'survival_reason': survival.reason,
                'intent_channel': intent.channel,
                'action_type': intent.action_type,
                'approved_budget': approved_budget,
                'requested_budget': assessment.requested_budget,
                'total_encumbrance': assessment.total_encumbrance,
                'runway_days_after_action': assessment.runway_days_after_action,
                'inference_capacity_policy': inference_policy,
            },
        )

    @staticmethod
    def _dedupe_checks(checks: list[PolicyCheckResult]) -> tuple[PolicyCheckResult, ...]:
        seen: set[tuple[str, str, str]] = set()
        ordered: list[PolicyCheckResult] = []
        for check in checks:
            token = (check.policy_name, check.status, check.reason)
            if token in seen:
                continue
            seen.add(token)
            ordered.append(check)
        return tuple(ordered)

    @staticmethod
    def _approved_budget(*, unique_checks: tuple[PolicyCheckResult, ...], assessment: Any) -> float:
        approved = max(0.0, float(getattr(assessment, 'requested_budget', 0.0)))
        for check in unique_checks:
            if check.policy_name == 'spend_cap_policy':
                hard_cap = float(check.details.get('hard_cap') or 0.0)
                if hard_cap > 0.0:
                    approved = min(approved, hard_cap)
        return approved


    def _inference_capacity_policy(self, *, decision: Any, assessment: Any) -> dict[str, Any]:
        payload = getattr(decision, 'payload', None)
        envelope = InferencePolicyEnvelope.from_payload(payload if isinstance(payload, dict) else {})
        roi_guard = InferenceROIGuard()
        runway_guard = InferenceRunwayGuard()
        policy_guard = InferencePolicyGuard()
        verdict = policy_guard.evaluate(envelope)
        roi_allowed = roi_guard.allows(
            expected_benefit_usd=float(envelope.expected_benefit_usd),
            expected_cost_usd=float(envelope.estimated_cost_usd),
        )
        runway_allowed = runway_guard.allows(
            runway_days_remaining=int(getattr(assessment, 'runway_days_after_action', 0) or 0),
        )
        return {
            'allowed': bool(verdict.allowed and roi_allowed and runway_allowed),
            'reason': verdict.reason if verdict.allowed and roi_allowed and runway_allowed else (
                'inference_policy_guard' if not verdict.allowed else 'inference_economic_guard'
            ),
            'requires_human_review': bool(verdict.requires_human_review),
            'roi_allowed': bool(roi_allowed),
            'runway_allowed': bool(runway_allowed),
            'metadata': dict(verdict.metadata),
        }
