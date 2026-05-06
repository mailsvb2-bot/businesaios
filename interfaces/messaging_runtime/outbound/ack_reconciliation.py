from __future__ import annotations

from .provider_ack_store import ProviderAckRecord


class ProviderAckReconciliationService:
    def __init__(self, *, ack_store, attempt_store, telemetry) -> None:
        self._ack_store = ack_store
        self._attempt_store = attempt_store
        self._telemetry = telemetry

    def reconcile(self, *, provider_message_id: str, dedupe_key: str, channel: str, status: str) -> dict:
        existing = self._ack_store.get(provider_message_id)
        if existing is not None:
            return {"status": "duplicate_ack", "provider_message_id": provider_message_id, "dedupe_key": existing.dedupe_key}

        self._ack_store.put(
            ProviderAckRecord(
                provider_message_id=provider_message_id,
                dedupe_key=dedupe_key,
                channel=channel,
                status=status,
            )
        )
        state = self._attempt_store.get(dedupe_key)
        correlation_id = dedupe_key
        if state is not None:
            correlation_id = state.correlation_id
            self._attempt_store.upsert(
                type(state)(
                    dedupe_key=state.dedupe_key,
                    correlation_id=state.correlation_id,
                    channel=state.channel,
                    attempt_count=state.attempt_count,
                    last_error=state.last_error,
                    status=status,
                )
            )
        self._telemetry.emit(
            event_name="provider_ack_reconciled",
            correlation_id=correlation_id,
            channel=channel,
            severity="info",
            component="delivery.ack_reconciliation",
            payload={"provider_message_id": provider_message_id, "dedupe_key": dedupe_key, "status": status},
        )
        return {"status": "ack_recorded", "provider_message_id": provider_message_id, "dedupe_key": dedupe_key}
