from __future__ import annotations

from execution.inference_budget_policy import InferenceBudgetPolicy
from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_cooldown_policy import InferenceCooldownPolicy
from execution.inference_escalation_decision_contract import InferenceEscalationAction, InferenceEscalationDecision
from execution.inference_scaling_signal_contract import InferenceScalingSignalSnapshot
from execution.inference_sla_policy import InferenceSLAPolicy


CANON_INFERENCE_ESCALATION_ENGINE = True


class InferenceEscalationEngine:

    def _acceleration_pressure_wants_escalation(self, signals: InferenceScalingSignalSnapshot) -> bool:
        return (
            float(signals.acceleration_saturation_score) >= 0.85
            or int(signals.acceleration_expected_queue_penalty_ms) >= 25
        )

    def _acceleration_pressure_blocks_deescalation(self, signals: InferenceScalingSignalSnapshot) -> bool:
        return (
            float(signals.acceleration_saturation_score) >= 0.50
            or int(signals.acceleration_expected_queue_penalty_ms) >= 15
            or str(signals.acceleration_locality_scope).strip() in {'distributed_remote', 'external_remote'}
        )

    def __init__(
        self,
        *,
        sla_policy: InferenceSLAPolicy | None = None,
        budget_policy: InferenceBudgetPolicy | None = None,
        cooldown_policy: InferenceCooldownPolicy | None = None,
    ) -> None:
        self._sla_policy = sla_policy or InferenceSLAPolicy()
        self._budget_policy = budget_policy or InferenceBudgetPolicy()
        self._cooldown_policy = cooldown_policy or InferenceCooldownPolicy()

    def evaluate(
        self,
        *,
        current_tier: InferenceCapacityTier,
        signals: InferenceScalingSignalSnapshot,
    ) -> InferenceEscalationDecision:
        tiers = list(InferenceCapacityTier)
        current_index = tiers.index(current_tier)
        wants_escalation = self._sla_policy.wants_escalation(signals) or self._acceleration_pressure_wants_escalation(signals)
        if wants_escalation:
            if self._budget_policy.allows_upgrade(
                budget_headroom_usd=signals.budget_headroom_usd,
                burn_rate_usd_per_hour=signals.spend_burn_rate_usd_per_hour,
            ):
                reason = 'SLA pressure and economic headroom justify deterministic capacity upgrade.'
                if self._acceleration_pressure_wants_escalation(signals):
                    reason = 'Acceleration pressure and economic headroom justify deterministic capacity upgrade.'
                return InferenceEscalationDecision(
                    action=InferenceEscalationAction.ESCALATE,
                    target_tier=tiers[min(current_index + 1, len(tiers) - 1)],
                    reason=reason,
                    cooldown_seconds=self._cooldown_policy.escalate_cooldown_seconds,
                )
        if self._sla_policy.wants_deescalation(signals) and not self._acceleration_pressure_blocks_deescalation(signals):
            return InferenceEscalationDecision(
                action=InferenceEscalationAction.DEESCALATE,
                target_tier=tiers[max(current_index - 1, 0)],
                reason='Load normalized and excess capacity can be reduced safely.',
                cooldown_seconds=self._cooldown_policy.deescalate_cooldown_seconds,
            )
        return InferenceEscalationDecision(
            action=InferenceEscalationAction.STAY,
            target_tier=current_tier,
            reason='Current inference capacity tier remains appropriate.',
            cooldown_seconds=0,
        )
    decide = evaluate
