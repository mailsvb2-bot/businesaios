from __future__ import annotations

"""Recovery policy engine.

Deterministic infra-grade classification over rebuilt durable run facts.

Important:
- no business strategy
- no planner
- no second brain
- only recovery action selection for the canonical execution path
"""

from dataclasses import dataclass, field

from reliability.dead_letter_policy import DeadLetterDecision, DeadLetterPolicy
from reliability.execution_checkpoint_store import ExecutionCheckpointStore
from reliability.idempotency_contract import IdempotencyKey, IdempotencyState, IdempotencyStore
from reliability.job_recovery_policy import JobRecoveryPolicy
from reliability.outbox_store import OutboxState, OutboxStore
from reliability.recovery_run_rebuilder import RebuiltRunFacts, RecoveryRunRebuilder


CANON_RECOVERY_POLICY_ENGINE = True
CANON_RECOVERY_POLICY_RESOLVE_ONLY = True


@dataclass(frozen=True)
class RecoveryPolicyConfig:
    quarantine_on_any_anomaly: bool = True
    quarantine_on_graph_invalidity: bool = True
    prefer_resume_delivery_on_claimable_outbox: bool = True
    prefer_wait_on_live_lease: bool = True
    allow_resume_delivery_after_failed_stage: bool = False
    allow_noop_on_terminal_completed_without_outbox: bool = True
    require_operator_review_for_dead_outbox: bool = True
    allow_partial_history_resume: bool = True
    quarantine_on_explicit_reference_drift: bool = True


@dataclass(frozen=True)
class RecoveryPolicyDecision:
    run_id: str
    action: str
    reason: str

    operator_required: bool = False
    retry_delay_seconds: int | None = None
    dead_letter_reason: str | None = None

    resume_action: str | None = None
    resume_stage: str | None = None
    delivery_hint: str | None = None
    operator_hint: str | None = None
    risk_flags: tuple[str, ...] = field(default_factory=tuple)

    anomalies: tuple[str, ...] = field(default_factory=tuple)
    rebuilt_facts: RebuiltRunFacts | None = None


class RecoveryPolicyEngine:
    def __init__(
        self,
        *,
        checkpoint_store: ExecutionCheckpointStore,
        idempotency_store: IdempotencyStore,
        outbox_store: OutboxStore,
        recovery_policy: JobRecoveryPolicy | None = None,
        dead_letter_policy: DeadLetterPolicy | None = None,
        config: RecoveryPolicyConfig | None = None,
    ) -> None:
        self._idempotency = idempotency_store
        self._rebuilder = RecoveryRunRebuilder(
            checkpoint_store=checkpoint_store,
            idempotency_store=idempotency_store,
            outbox_store=outbox_store,
        )
        self._recovery_policy = recovery_policy or JobRecoveryPolicy()
        self._dead_letter_policy = dead_letter_policy or DeadLetterPolicy()
        self._config = config or RecoveryPolicyConfig()

    def resolve(
        self,
        *,
        tenant_id: str,
        run_id: str,
        idempotency_key: IdempotencyKey | None = None,
        outbox_message_id: str | None = None,
    ) -> RecoveryPolicyDecision:
        facts = self._rebuilder.rebuild(
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
        )

        if facts.partial_history_detected and not self._config.allow_partial_history_resume:
            return self._decision(
                facts=facts,
                action="quarantine",
                reason="partial_history_not_allowed_by_policy",
                operator_required=True,
                operator_hint="earlier checkpoints are missing; inspect durability path before replay",
            )

        if self._config.quarantine_on_graph_invalidity and not facts.graph_validation.is_valid:
            return self._decision(
                facts=facts,
                action="quarantine",
                reason="invalid_execution_graph",
                operator_required=True,
                operator_hint="inspect checkpoint topology and run lineage",
            )

        reference_drift_codes = {
            "requested_outbox_message_id_mismatch",
            "requested_idempotency_key_mismatch",
            "latest_checkpoint_outbox_message_id_mismatch",
            "latest_checkpoint_idempotency_key_mismatch",
        }
        if self._config.quarantine_on_explicit_reference_drift and any(code in facts.anomalies for code in reference_drift_codes):
            return self._decision(
                facts=facts,
                action="quarantine",
                reason="explicit_reference_drift",
                operator_required=True,
                operator_hint="caller-provided recovery references disagree with durable history",
            )

        if self._config.quarantine_on_any_anomaly and facts.anomalies:
            return self._decision(
                facts=facts,
                action="quarantine",
                reason="reconciliation_anomaly",
                operator_required=True,
                operator_hint="inspect rebuilt run facts and durable store consistency",
            )

        if facts.latest_stage == "completed":
            if facts.idempotency_record is not None and facts.idempotency_record.state is not IdempotencyState.COMPLETED:
                return self._decision(
                    facts=facts,
                    action="quarantine",
                    reason="completed_checkpoint_without_completed_idempotency",
                    operator_required=True,
                    operator_hint="run reached completed checkpoint but idempotency is not terminal-completed",
                )

            if facts.outbox_message is not None and not facts.outbox_is_delivered:
                dead = self._classify_dead_letter(facts)
                if dead is not None and dead.move_to_dead_letter:
                    return self._decision(
                        facts=facts,
                        action="move_to_dead_letter",
                        reason="completed_checkpoint_with_non_delivered_outbox_dead_lettered",
                        operator_required=False,
                        retry_delay_seconds=dead.retry_delay_seconds,
                        dead_letter_reason=dead.reason,
                        delivery_hint="outbox_not_delivered",
                    )
                return self._decision(
                    facts=facts,
                    action="quarantine",
                    reason="completed_checkpoint_without_delivered_outbox",
                    operator_required=True,
                    dead_letter_reason=None if dead is None else dead.reason,
                    delivery_hint="outbox_not_delivered",
                    operator_hint="completed run should not have non-delivered outbox",
                )

            if facts.outbox_message is None and not self._config.allow_noop_on_terminal_completed_without_outbox:
                return self._decision(
                    facts=facts,
                    action="quarantine",
                    reason="completed_checkpoint_without_outbox_record",
                    operator_required=True,
                    operator_hint="decide whether this run type is allowed to complete without outbox",
                )

            return self._decision(
                facts=facts,
                action="noop",
                reason="terminal_completed",
                operator_required=False,
            )

        if facts.latest_stage == "failed":
            if facts.outbox_message is not None and facts.outbox_is_claimable and self._config.allow_resume_delivery_after_failed_stage:
                return self._decision(
                    facts=facts,
                    action="resume_delivery",
                    reason="failed_checkpoint_but_claimable_outbox_allowed_by_policy",
                    operator_required=False,
                    delivery_hint="claimable_outbox",
                )

            dead = self._classify_dead_letter(facts)
            if dead is not None and dead.move_to_dead_letter:
                return self._decision(
                    facts=facts,
                    action="move_to_dead_letter",
                    reason="terminal_failed_dead_letter",
                    operator_required=False,
                    retry_delay_seconds=dead.retry_delay_seconds,
                    dead_letter_reason=dead.reason,
                    delivery_hint="dead_letter_candidate",
                )

            return self._decision(
                facts=facts,
                action="quarantine",
                reason="terminal_failed_requires_operator_review",
                operator_required=True,
                dead_letter_reason=None if dead is None else dead.reason,
                operator_hint="terminal failed run requires operator inspection",
            )

        if self._config.prefer_resume_delivery_on_claimable_outbox and facts.outbox_is_claimable and facts.latest_stage in {
            "execution",
            "verification",
            "state_update",
            "evidence",
        }:
            return self._decision(
                facts=facts,
                action="resume_delivery",
                reason=f"claimable_outbox_after_{facts.latest_stage}",
                operator_required=False,
                delivery_hint="claimable_outbox",
            )

        if self._config.prefer_wait_on_live_lease and facts.has_live_idempotency_lease:
            return self._decision(
                facts=facts,
                action="wait",
                reason="live_idempotency_lease",
                operator_required=False,
            )

        if facts.outbox_is_dead:
            return self._decision(
                facts=facts,
                action="quarantine" if self._config.require_operator_review_for_dead_outbox else "noop",
                reason="outbox_already_dead",
                operator_required=self._config.require_operator_review_for_dead_outbox,
                delivery_hint="dead_outbox",
                operator_hint="dead outbox usually means prior recovery or delivery exhaustion",
            )

        coarse = self._recovery_policy.classify(
            latest_stage=facts.latest_stage,
            outbox_claimable=facts.outbox_is_claimable,
            idempotency_in_progress=facts.has_live_idempotency_lease,
            anomalies_present=bool(facts.anomalies),
        )

        delivery_hint = None
        if facts.outbox_message is not None:
            if facts.outbox_message.state is OutboxState.DELIVERING and facts.outbox_message.is_claim_expired():
                delivery_hint = "expired_delivery_claim"
            elif facts.outbox_message.state is OutboxState.PENDING:
                delivery_hint = "pending_delivery"
            elif facts.outbox_message.state is OutboxState.DELIVERED:
                delivery_hint = "already_delivered"

        return self._decision(
            facts=facts,
            action=coarse.action,
            reason=coarse.reason,
            operator_required=coarse.action == "quarantine",
            delivery_hint=delivery_hint,
            operator_hint="coarse recovery policy classification" if coarse.action == "quarantine" else None,
        )

    def _decision(
        self,
        *,
        facts: RebuiltRunFacts,
        action: str,
        reason: str,
        operator_required: bool,
        retry_delay_seconds: int | None = None,
        dead_letter_reason: str | None = None,
        delivery_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> RecoveryPolicyDecision:
        risk_flags = self._build_risk_flags(facts=facts)
        return RecoveryPolicyDecision(
            run_id=facts.run_id,
            action=action,
            reason=reason,
            operator_required=operator_required,
            retry_delay_seconds=retry_delay_seconds,
            dead_letter_reason=dead_letter_reason,
            resume_action=facts.resume_point.action,
            resume_stage=facts.resume_point.stage,
            delivery_hint=delivery_hint,
            operator_hint=operator_hint,
            risk_flags=risk_flags,
            anomalies=facts.anomalies,
            rebuilt_facts=facts,
        )

    def _build_risk_flags(self, *, facts: RebuiltRunFacts) -> tuple[str, ...]:
        flags: list[str] = []
        if facts.partial_history_detected:
            flags.append("partial_history")
        if facts.outbox_message is not None and facts.outbox_message.is_claimable():
            flags.append("claimable_outbox")
        if facts.has_live_idempotency_lease:
            flags.append("live_idempotency_lease")
        if bool(facts.derived_flags.get("claimable_outbox_while_idempotency_lease_live")):
            flags.append("claimable_outbox_while_idempotency_lease_live")
        if facts.outbox_is_dead:
            flags.append("dead_outbox")
        if facts.is_terminal:
            flags.append("terminal_run")
        if facts.graph_validation.skipped_forward_stages:
            flags.append("skipped_forward_stages")
        return tuple(flags)

    def _classify_dead_letter(self, facts: RebuiltRunFacts) -> DeadLetterDecision | None:
        message = facts.outbox_message
        if message is None or not message.last_error:
            return None
        return self._dead_letter_policy.classify(
            message=message,
            error=message.last_error,
            retryable=True,
        )


__all__ = [
    "CANON_RECOVERY_POLICY_ENGINE",
    "CANON_RECOVERY_POLICY_RESOLVE_ONLY",
    "RecoveryPolicyConfig",
    "RecoveryPolicyDecision",
    "RecoveryPolicyEngine",
]
