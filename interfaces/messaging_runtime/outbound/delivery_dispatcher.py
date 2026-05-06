from __future__ import annotations

from interfaces.messaging_runtime.channel_factory import TransportSendNotConfigured

from .models import DeadLetterRecord, DeliveryAttemptState


class DeliveryDispatcher:
    def __init__(self, *, registry, queue_service, telemetry, retry_policy, attempt_store, dead_letter_store) -> None:
        self._registry = registry
        self._queue_service = queue_service
        self._telemetry = telemetry
        self._retry_policy = retry_policy
        self._attempt_store = attempt_store
        self._dead_letter_store = dead_letter_store

    async def dispatch_once(self) -> dict | None:
        item = self._queue_service.dequeue()
        if item is None:
            return None

        previous = self._attempt_store.get(item.dedupe_key)
        attempt_count = 1 if previous is None else previous.attempt_count + 1
        self._attempt_store.upsert(
            DeliveryAttemptState(
                dedupe_key=item.dedupe_key,
                correlation_id=item.correlation_id,
                channel=item.channel,
                attempt_count=attempt_count,
                last_error=None,
                status="dispatching",
            )
        )
        self._telemetry.emit(
            event_name="delivery_dispatch_started",
            correlation_id=item.correlation_id,
            channel=item.channel,
            severity="info",
            component="delivery.dispatcher",
            payload={"attempt_count": attempt_count, "dedupe_key": item.dedupe_key},
        )

        try:
            result = await self._registry.get(item.channel).send_outbound(item)
            self._attempt_store.upsert(
                DeliveryAttemptState(
                    dedupe_key=item.dedupe_key,
                    correlation_id=item.correlation_id,
                    channel=item.channel,
                    attempt_count=attempt_count,
                    last_error=None,
                    status="delivered",
                )
            )
            self._queue_service.release(item.dedupe_key)
            self._telemetry.emit(
                event_name="delivery_success",
                correlation_id=item.correlation_id,
                channel=item.channel,
                severity="info",
                component="delivery.dispatcher",
                payload={"attempt_count": attempt_count},
            )
            return result
        except TransportSendNotConfigured as exc:
            self._attempt_store.upsert(
                DeliveryAttemptState(
                    dedupe_key=item.dedupe_key,
                    correlation_id=item.correlation_id,
                    channel=item.channel,
                    attempt_count=attempt_count,
                    last_error=str(exc),
                    status="transport_not_configured",
                )
            )
            self._queue_service.release(item.dedupe_key)
            self._telemetry.emit(
                event_name="delivery_transport_not_configured",
                correlation_id=item.correlation_id,
                channel=item.channel,
                severity="critical",
                component="delivery.dispatcher",
                payload={"attempt_count": attempt_count, "reason": str(exc)},
            )
            raise
        except Exception as exc:
            decision = self._retry_policy.evaluate(attempt_count=attempt_count, exc=exc)
            self._attempt_store.upsert(
                DeliveryAttemptState(
                    dedupe_key=item.dedupe_key,
                    correlation_id=item.correlation_id,
                    channel=item.channel,
                    attempt_count=attempt_count,
                    last_error=str(exc),
                    status=decision.action,
                )
            )
            severity = "error" if decision.action == "dead_letter" else "warning"
            self._telemetry.emit(
                event_name="delivery_failure",
                correlation_id=item.correlation_id,
                channel=item.channel,
                severity=severity,
                component="delivery.dispatcher",
                payload={"attempt_count": attempt_count, "action": decision.action, "reason": decision.reason},
            )
            self._queue_service.release(item.dedupe_key)
            if decision.action in {"retry", "defer"}:
                self._queue_service.enqueue(item)
                return {"status": decision.action, "reason": decision.reason}

            self._dead_letter_store.put(
                DeadLetterRecord(
                    dedupe_key=item.dedupe_key,
                    correlation_id=item.correlation_id,
                    channel=item.channel,
                    reason=decision.reason,
                    metadata={"body": item.body},
                )
            )
            return {"status": "dead_letter", "reason": decision.reason}
