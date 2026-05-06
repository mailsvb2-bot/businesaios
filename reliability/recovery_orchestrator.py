from __future__ import annotations

"""Recovery orchestrator for the canonical execution path.

No business logic, no second brain, no strategic decisions.
Only recovery-state planning and transport delivery recovery orchestration.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from reliability.dead_letter_policy import DeadLetterPolicy
from reliability.execution_checkpoint_store import ExecutionCheckpointStore
from reliability.execution_reconciliation import ExecutionReconciliation, ReconciliationReport
from reliability.idempotency_contract import IdempotencyKey, IdempotencyStore
from reliability.job_recovery_policy import JobRecoveryPolicy
from reliability.outbox_store import OutboxState, OutboxStore
from reliability.outbox_worker_contract import GlobalOutboxDeliveryReport, GlobalOutboxWorker
from reliability.recovery_policy_engine import RecoveryPolicyConfig, RecoveryPolicyEngine


CANON_RECOVERY_ORCHESTRATOR = True


@dataclass(frozen=True)
class RecoveryPlan:
    run_id: str
    recovery_action: str
    reason: str
    reconciliation: ReconciliationReport
    anomalies: tuple[str, ...] = field(default_factory=tuple)
    delivery_hint: str | None = None
    dead_letter_hint: str | None = None
    operator_required: bool = False
    operator_hint: str | None = None
    resume_action: str | None = None
    resume_stage: str | None = None
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    policy_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportRecoveryResult:
    transport_name: str
    worker_id: str
    backend_name: str
    processed: int
    delivered: int
    retried: int
    dead_lettered: int
    skipped: int


class RecoveryOrchestrator:
    def __init__(
        self,
        *,
        checkpoint_store: ExecutionCheckpointStore,
        idempotency_store: IdempotencyStore,
        outbox_store: OutboxStore,
        recovery_policy: JobRecoveryPolicy | None = None,
        dead_letter_policy: DeadLetterPolicy | None = None,
        transport_workers: Mapping[str, GlobalOutboxWorker] | None = None,
        policy_config: RecoveryPolicyConfig | None = None,
    ) -> None:
        self._checkpoints = checkpoint_store
        self._idempotency = idempotency_store
        self._outbox = outbox_store
        self._recovery_policy = recovery_policy or JobRecoveryPolicy()
        self._dead_letter_policy = dead_letter_policy or DeadLetterPolicy()
        self._reconciliation = ExecutionReconciliation(
            checkpoint_store=checkpoint_store,
            idempotency_store=idempotency_store,
            outbox_store=outbox_store,
        )
        self._policy_engine = RecoveryPolicyEngine(
            checkpoint_store=checkpoint_store,
            idempotency_store=idempotency_store,
            outbox_store=outbox_store,
            recovery_policy=self._recovery_policy,
            dead_letter_policy=self._dead_letter_policy,
            config=policy_config,
        )
        self._transport_workers = dict(transport_workers or {})

    def register_transport_worker(self, *, transport_name: str, worker: GlobalOutboxWorker) -> None:
        key = str(transport_name or "").strip()
        if not key:
            raise ValueError("transport_name is required")
        self._transport_workers[key] = worker

    def reconcile(
        self,
        *,
        tenant_id: str,
        run_id: str,
        idempotency_key: IdempotencyKey | None = None,
        outbox_message_id: str | None = None,
    ) -> ReconciliationReport:
        return self._reconciliation.reconcile(
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
        )

    def plan(
        self,
        *,
        tenant_id: str,
        run_id: str,
        idempotency_key: IdempotencyKey | None = None,
        outbox_message_id: str | None = None,
    ) -> RecoveryPlan:
        reconciliation = self._reconciliation.reconcile(
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
        )
        decision = self._policy_engine.resolve(
            tenant_id=tenant_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            outbox_message_id=outbox_message_id,
        )

        delivery_hint = decision.delivery_hint
        rebuilt = decision.rebuilt_facts
        if delivery_hint == "claimable_outbox" and rebuilt is not None and rebuilt.outbox_message is not None:
            outbox_message = rebuilt.outbox_message
            if outbox_message.state is OutboxState.PENDING:
                delivery_hint = "pending_delivery_can_be_claimed"
            elif outbox_message.state is OutboxState.DELIVERING and outbox_message.is_claim_expired():
                delivery_hint = "expired_delivery_claim_can_be_stolen"
        elif delivery_hint == "expired_delivery_claim":
            delivery_hint = "expired_delivery_claim_can_be_stolen"
        elif delivery_hint == "pending_delivery":
            delivery_hint = "pending_delivery_can_be_claimed"

        dead_letter_hint = decision.dead_letter_reason
        if dead_letter_hint is None and rebuilt is not None and rebuilt.outbox_message is not None and rebuilt.outbox_message.last_error:
            dead_letter_hint = self._dead_letter_policy.classify(
                message=rebuilt.outbox_message,
                error=rebuilt.outbox_message.last_error,
                retryable=True,
            ).reason

        return RecoveryPlan(
            run_id=str(run_id),
            recovery_action=decision.action,
            reason=decision.reason,
            reconciliation=reconciliation,
            anomalies=decision.anomalies or reconciliation.anomalies,
            delivery_hint=delivery_hint,
            dead_letter_hint=dead_letter_hint,
            operator_required=decision.operator_required,
            operator_hint=decision.operator_hint,
            resume_action=decision.resume_action,
            resume_stage=decision.resume_stage,
            risk_flags=decision.risk_flags,
            policy_snapshot={
                "resume_action": decision.resume_action,
                "resume_stage": decision.resume_stage,
                "delivery_hint": delivery_hint,
                "dead_letter_hint": dead_letter_hint,
                "risk_flags": list(decision.risk_flags or ()),
            },
        )

    def recover_all_transports(
        self,
        *,
        tenant_id: str,
        max_batches: int = 100,
    ) -> GlobalOutboxDeliveryReport:
        worker_reports = []
        delivered = retried = dead_lettered = skipped = processed = 0

        for transport_name in sorted(self._transport_workers.keys()):
            worker = self._transport_workers[transport_name]
            report = worker.run_until_drained(tenant_id=tenant_id, max_batches=max_batches)
            worker_reports.append(report)
            processed += int(getattr(report, "processed", 0))
            delivered += int(getattr(report, "delivered", 0))
            retried += int(getattr(report, "retried", 0))
            dead_lettered += int(getattr(report, "dead_lettered", 0))
            skipped += int(getattr(report, "skipped", 0))

        return GlobalOutboxDeliveryReport(
            tenant_id=str(tenant_id),
            processed=processed,
            delivered=delivered,
            retried=retried,
            dead_lettered=dead_lettered,
            skipped=skipped,
            worker_reports=tuple(worker_reports),
        )

    def recover_transport(
        self,
        *,
        tenant_id: str,
        transport_name: str,
        max_batches: int = 100,
    ) -> TransportRecoveryResult:
        key = str(transport_name or "").strip()
        if key not in self._transport_workers:
            raise KeyError(f"unknown transport worker: {key}")
        worker = self._transport_workers[key]
        report = worker.run_until_drained(tenant_id=tenant_id, max_batches=max_batches)
        descriptor = worker.descriptor()
        return TransportRecoveryResult(
            transport_name=descriptor.transport_name,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            processed=int(getattr(report, "processed", 0)),
            delivered=int(getattr(report, "delivered", 0)),
            retried=int(getattr(report, "retried", 0)),
            dead_lettered=int(getattr(report, "dead_lettered", 0)),
            skipped=int(getattr(report, "skipped", 0)),
        )


__all__ = [
    "CANON_RECOVERY_ORCHESTRATOR",
    "RecoveryOrchestrator",
    "RecoveryPlan",
    "TransportRecoveryResult",
]
