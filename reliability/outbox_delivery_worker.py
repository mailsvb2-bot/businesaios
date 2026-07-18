from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from observability.delivery_metrics import DeliveryObservabilityMetrics
from reliability.dead_letter_policy import DeadLetterPolicy
from reliability.outbox_backend import (
    OutboxBackend,
    OutboxDeliveryConflict,
    OutboxDeliveryError,
    OutboxDeliveryReceipt,
)
from reliability.outbox_store import OutboxMessage, OutboxState, OutboxStore
from reliability.outbox_worker_contract import OutboxWorkerDescriptor


CANON_OUTBOX_DELIVERY_WORKER = True


_FATAL_ERROR_CODES = {"delivery_conflict", "poison_message", "schema_mismatch"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _transport_name_from_message(message: OutboxMessage, *, fallback: str) -> str:
    metadata = dict(message.delivery_metadata or {})
    for key in ("transport", "channel", "transport_name"):
        value = metadata.get(key)
        if str(value or "").strip():
            return str(value).strip()
    payload = dict(message.payload or {})
    for key in ("transport", "channel", "transport_name"):
        value = payload.get(key)
        if str(value or "").strip():
            return str(value).strip()
    topic = str(message.topic or "").strip()
    return topic or (str(fallback or "outbox").strip() or "outbox")


@dataclass(frozen=True)
class OutboxDeliveryAttemptReport:
    tenant_id: str
    message_id: str
    final_state: str
    success: bool
    attempts_before: int
    attempts_after: int
    error: str | None = None
    receipt: OutboxDeliveryReceipt | None = None
    topic: str | None = None
    transport_name: str | None = None


@dataclass(frozen=True)
class OutboxDeliveryRunReport:
    worker_id: str
    tenant_id: str
    processed: int = 0
    delivered: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped: int = 0
    reports: tuple[OutboxDeliveryAttemptReport, ...] = field(default_factory=tuple)
    backend_name: str | None = None
    transport_name: str | None = None


class OutboxDeliveryWorker:
    """
    Infrastructure-only outbox delivery worker.

    It never creates business decisions and never bypasses the canonical
    outbox state machine. It only claims, delivers, and writes final state.
    """

    def __init__(
        self,
        *,
        outbox_store: OutboxStore,
        backend: OutboxBackend,
        dead_letter_policy: DeadLetterPolicy | None = None,
        worker_id: str = "outbox-delivery-worker",
        transport_name: str | None = None,
        claim_ttl_seconds: int = 60,
        batch_limit: int = 100,
        max_consecutive_failures: int = 25,
        now_factory: Callable[[], datetime] | None = None,
        metrics: DeliveryObservabilityMetrics | None = None,
    ) -> None:
        self._store = outbox_store
        self._backend = backend
        self._dead_letter_policy = dead_letter_policy or DeadLetterPolicy()
        self._worker_id = str(worker_id).strip() or "outbox-delivery-worker"
        requested_transport = str(transport_name or "").strip()
        backend_transport = str(getattr(backend, "backend_name", "outbox") or "").strip()
        self._transport_name = requested_transport or backend_transport or "outbox"
        self._claim_ttl_seconds = max(1, int(claim_ttl_seconds))
        self._batch_limit = max(1, int(batch_limit))
        self._max_consecutive_failures = max(1, int(max_consecutive_failures))
        self._now_factory = now_factory or utc_now
        self._metrics = metrics

    def descriptor(self) -> OutboxWorkerDescriptor:
        descriptor = OutboxWorkerDescriptor(
            worker_id=self._worker_id,
            transport_name=self._transport_name,
            backend_name=str(getattr(self._backend, "backend_name", self._transport_name)),
        )
        descriptor.validate()
        return descriptor

    def run_once(self, *, tenant_id: str, limit: int | None = None) -> OutboxDeliveryRunReport:
        descriptor = self.descriptor()
        try:
            health = self._backend.healthcheck()
            health.validate()
        except Exception as exc:
            if self._metrics is not None:
                self._metrics.record_skipped(
                    tenant_id=str(tenant_id),
                    transport_name=descriptor.transport_name,
                    backend_name=descriptor.backend_name,
                    reason="healthcheck_exception",
                )
            return OutboxDeliveryRunReport(
                worker_id=self._worker_id,
                tenant_id=str(tenant_id),
                processed=0,
                skipped=1,
                reports=(
                    OutboxDeliveryAttemptReport(
                        tenant_id=str(tenant_id),
                        message_id="<backend-healthcheck>",
                        final_state=OutboxState.PENDING.value,
                        success=False,
                        attempts_before=0,
                        attempts_after=0,
                        error=f"{type(exc).__name__}: {exc}",
                        transport_name=descriptor.transport_name,
                    ),
                ),
                backend_name=descriptor.backend_name,
                transport_name=descriptor.transport_name,
            )
        if self._metrics is not None:
            self._metrics.record_worker_healthcheck(
                tenant_id=str(tenant_id),
                transport_name=descriptor.transport_name,
                backend_name=descriptor.backend_name,
                healthy=bool(health.healthy),
            )
        if not health.healthy:
            if self._metrics is not None:
                self._metrics.record_skipped(
                    tenant_id=str(tenant_id),
                    transport_name=descriptor.transport_name,
                    backend_name=descriptor.backend_name,
                    reason="backend_unhealthy",
                )
            return OutboxDeliveryRunReport(
                worker_id=self._worker_id,
                tenant_id=str(tenant_id),
                processed=0,
                skipped=1,
                reports=(
                    OutboxDeliveryAttemptReport(
                        tenant_id=str(tenant_id),
                        message_id="<backend-unhealthy>",
                        final_state=OutboxState.PENDING.value,
                        success=False,
                        attempts_before=0,
                        attempts_after=0,
                        error=f"backend unhealthy: {health.detail}",
                        transport_name=descriptor.transport_name,
                    ),
                ),
                backend_name=descriptor.backend_name,
                transport_name=descriptor.transport_name,
            )

        max_items = self._batch_limit if limit is None else max(0, int(limit))
        claimable = () if max_items == 0 else self._store.list_claimable(tenant_id=tenant_id, limit=max_items, now=self._now_factory())

        reports: list[OutboxDeliveryAttemptReport] = []
        delivered = 0
        retried = 0
        dead_lettered = 0
        skipped = 0
        consecutive_failures = 0

        for item in claimable:
            claimed = self._store.claim(
                tenant_id=item.tenant_id,
                message_id=item.message_id,
                owner_id=self._worker_id,
                claim_ttl_seconds=self._claim_ttl_seconds,
                now=self._now_factory(),
            )
            if claimed is None:
                skipped += 1
                continue
            if self._metrics is not None:
                self._metrics.record_claimed(
                    tenant_id=claimed.tenant_id,
                    transport_name=_transport_name_from_message(claimed, fallback=descriptor.transport_name),
                    backend_name=descriptor.backend_name,
                    topic=claimed.topic,
                )

            report = self._deliver_claimed(claimed)
            reports.append(report)

            if report.success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= self._max_consecutive_failures:
                    break

            if report.final_state == OutboxState.DELIVERED.value:
                delivered += 1
            elif report.final_state == OutboxState.PENDING.value:
                retried += 1
            elif report.final_state == OutboxState.DEAD.value:
                dead_lettered += 1
            else:
                skipped += 1

        run_report = OutboxDeliveryRunReport(
            worker_id=self._worker_id,
            tenant_id=str(tenant_id),
            processed=len(reports),
            delivered=delivered,
            retried=retried,
            dead_lettered=dead_lettered,
            skipped=skipped,
            reports=tuple(reports),
            backend_name=descriptor.backend_name,
            transport_name=descriptor.transport_name,
        )
        if self._metrics is not None:
            self._metrics.record_batch(
                tenant_id=str(tenant_id),
                transport_name=descriptor.transport_name,
                backend_name=descriptor.backend_name,
                processed=run_report.processed,
                delivered=run_report.delivered,
                retried=run_report.retried,
                dead_lettered=run_report.dead_lettered,
                skipped=run_report.skipped,
            )
        return run_report

    def run_until_drained(self, *, tenant_id: str, max_batches: int = 100) -> OutboxDeliveryRunReport:
        all_reports: list[OutboxDeliveryAttemptReport] = []
        delivered = retried = dead_lettered = skipped = 0

        for _ in range(max(0, int(max_batches))):
            report = self.run_once(tenant_id=tenant_id, limit=self._batch_limit)
            if report.processed == 0:
                break
            all_reports.extend(report.reports)
            delivered += report.delivered
            retried += report.retried
            dead_lettered += report.dead_lettered
            skipped += report.skipped

        descriptor = self.descriptor()
        return OutboxDeliveryRunReport(
            worker_id=self._worker_id,
            tenant_id=str(tenant_id),
            processed=len(all_reports),
            delivered=delivered,
            retried=retried,
            dead_lettered=dead_lettered,
            skipped=skipped,
            reports=tuple(all_reports),
            backend_name=descriptor.backend_name,
            transport_name=descriptor.transport_name,
        )

    def _deliver_claimed(self, message: OutboxMessage) -> OutboxDeliveryAttemptReport:
        attempts_before = max(0, int(message.delivery_attempts) - 1)
        descriptor = self.descriptor()
        transport_name = _transport_name_from_message(message, fallback=descriptor.transport_name)

        try:
            receipt = self._backend.deliver(message)
            receipt.validate()
            updated = self._store.mark_delivered(
                tenant_id=message.tenant_id,
                message_id=message.message_id,
                owner_id=self._worker_id,
                now=self._now_factory(),
                backend_name=receipt.backend_name,
                external_id=receipt.external_id,
                payload_digest=receipt.payload_digest,
                metadata=receipt.metadata,
            )
            if self._metrics is not None:
                self._metrics.record_delivered(
                    tenant_id=message.tenant_id,
                    transport_name=transport_name,
                    backend_name=descriptor.backend_name,
                    topic=message.topic,
                    attempts_after=updated.delivery_attempts,
                )
            return OutboxDeliveryAttemptReport(
                tenant_id=message.tenant_id,
                message_id=message.message_id,
                final_state=updated.state.value,
                success=True,
                attempts_before=attempts_before,
                attempts_after=updated.delivery_attempts,
                receipt=receipt,
                topic=message.topic,
                transport_name=transport_name,
            )

        except OutboxDeliveryConflict as exc:
            return self._handle_failure(message=message, error=exc, retryable=False)

        except OutboxDeliveryError as exc:
            retryable = exc.retryable and str(exc.code or "") not in _FATAL_ERROR_CODES
            return self._handle_failure(message=message, error=exc, retryable=retryable)

        except Exception as exc:  # fail-closed
            return self._handle_failure(message=message, error=exc, retryable=True)

    def _handle_failure(
        self,
        *,
        message: OutboxMessage,
        error: Exception,
        retryable: bool,
    ) -> OutboxDeliveryAttemptReport:
        decision = self._dead_letter_policy.classify(
            message=message,
            error=error,
            retryable=retryable,
            now=self._now_factory(),
        )

        error_text = f"{type(error).__name__}: {error}"
        descriptor = self.descriptor()
        transport_name = _transport_name_from_message(message, fallback=descriptor.transport_name)
        error_family = type(error).__name__

        if decision.move_to_dead_letter:
            updated = self._store.move_to_dead_letter(
                tenant_id=message.tenant_id,
                message_id=message.message_id,
                owner_id=self._worker_id,
                error=error_text,
                now=self._now_factory(),
            )
            if self._metrics is not None:
                self._metrics.record_dead_letter(
                    tenant_id=message.tenant_id,
                    transport_name=transport_name,
                    backend_name=descriptor.backend_name,
                    topic=message.topic,
                    error_family=error_family,
                )
            return OutboxDeliveryAttemptReport(
                tenant_id=message.tenant_id,
                message_id=message.message_id,
                final_state=updated.state.value,
                success=False,
                attempts_before=max(0, int(message.delivery_attempts) - 1),
                attempts_after=updated.delivery_attempts,
                error=error_text,
                topic=message.topic,
                transport_name=transport_name,
            )

        updated = self._store.schedule_retry(
            tenant_id=message.tenant_id,
            message_id=message.message_id,
            owner_id=self._worker_id,
            delay_seconds=max(1, int(decision.retry_delay_seconds or 1)),
            error=error_text,
            now=self._now_factory(),
        )
        if self._metrics is not None:
            self._metrics.record_retry(
                tenant_id=message.tenant_id,
                transport_name=transport_name,
                backend_name=descriptor.backend_name,
                topic=message.topic,
                error_family=error_family,
            )
        return OutboxDeliveryAttemptReport(
            tenant_id=message.tenant_id,
            message_id=message.message_id,
            final_state=updated.state.value,
            success=False,
            attempts_before=max(0, int(message.delivery_attempts) - 1),
            attempts_after=updated.delivery_attempts,
            error=error_text,
            topic=message.topic,
            transport_name=transport_name,
        )


__all__ = [
    "CANON_OUTBOX_DELIVERY_WORKER",
    "OutboxDeliveryAttemptReport",
    "OutboxDeliveryRunReport",
    "OutboxDeliveryWorker",
]
