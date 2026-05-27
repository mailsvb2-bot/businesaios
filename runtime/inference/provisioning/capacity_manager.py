from __future__ import annotations

from execution.inference_escalation_decision_contract import InferenceEscalationAction
from execution.inference_escalation_engine import InferenceEscalationEngine
from execution.inference_scaling_signal_contract import InferenceScalingSignalSnapshot
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore
from runtime.inference.provisioning.capacity_transition_journal import InferenceCapacityTransitionJournal
from runtime.inference.provisioning.upgrade_cooldown_tracker import InferenceUpgradeCooldownTracker


CANON_RUNTIME_INFERENCE_CAPACITY_MANAGER = True


class InferenceCapacityManager:
    def __init__(
        self,
        *,
        state_store: InferenceCapacityStateStore,
        escalation_engine: InferenceEscalationEngine,
        audit_log: InferenceEscalationAuditLog | None = None,
        transition_journal: InferenceCapacityTransitionJournal | None = None,
        cooldown_tracker: InferenceUpgradeCooldownTracker | None = None,
    ) -> None:
        self._state_store = state_store
        self._engine = escalation_engine
        self._audit_log = audit_log or InferenceEscalationAuditLog()
        self._transition_journal = transition_journal or InferenceCapacityTransitionJournal()
        self._cooldown_tracker = cooldown_tracker or InferenceUpgradeCooldownTracker()

    def evaluate(self, *, signals: InferenceScalingSignalSnapshot):
        capacity_state = self._state_store.get()
        if capacity_state.frozen:
            return capacity_state.active_tier, "capacity frozen by operator"
        decision = self._engine.evaluate(current_tier=capacity_state.active_tier, signals=signals)
        cooldown_key = f"{capacity_state.active_tier.value}:{decision.target_tier.value}:{decision.action.value}"
        if decision.cooldown_seconds and not self._cooldown_tracker.allow(cooldown_key):
            return capacity_state.active_tier, "cooldown active"
        if decision.action in (InferenceEscalationAction.ESCALATE, InferenceEscalationAction.DEESCALATE):
            previous_tier = capacity_state.active_tier
            self._state_store.set_tier(decision.target_tier)
            self._cooldown_tracker.arm(cooldown_key, decision.cooldown_seconds)
            self._audit_log.record(from_tier=previous_tier.value, to_tier=decision.target_tier.value, reason=decision.reason)
            self._transition_journal.record(from_tier=previous_tier.value, to_tier=decision.target_tier.value, reason=decision.reason)
        return self._state_store.get().active_tier, decision.reason
