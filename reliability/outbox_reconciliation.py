from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any, Iterable, Mapping
import json

from reliability.outbox_backend import OutboxBackendInspector, OutboxDeliveryRecord
from reliability.outbox_store import OutboxMessage, OutboxState, OutboxStore


CANON_OUTBOX_RECONCILIATION = True


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported json value: {type(value)!r}")


def _payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=_json_default, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OutboxReconciliationFinding:
    tenant_id: str
    message_id: str
    severity: str
    code: str
    detail: str


@dataclass(frozen=True)
class OutboxReconciliationReport:
    tenant_id: str
    checked: int
    findings: tuple[OutboxReconciliationFinding, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.findings


class OutboxReconciliation:
    """
    Audit-only reconciliation between canonical outbox state and delivery evidence.

    This component does not deliver, retry, mutate state, or create an alternative
    execution path. It only compares evidence.
    """

    def __init__(
        self,
        *,
        outbox_store: OutboxStore,
        backend: OutboxBackendInspector,
    ) -> None:
        self._store = outbox_store
        self._backend = backend

    def reconcile_message(self, *, tenant_id: str, message_id: str) -> OutboxReconciliationReport:
        message = self._store.get(tenant_id=tenant_id, message_id=message_id)
        backend_record = self._backend.get_record(tenant_id=tenant_id, message_id=message_id)
        findings = self._compare(
            tenant_id=str(tenant_id),
            message_id=str(message_id),
            message=message,
            backend_record=backend_record,
        )
        return OutboxReconciliationReport(
            tenant_id=str(tenant_id),
            checked=1,
            findings=tuple(findings),
        )

    def reconcile_messages(self, *, tenant_id: str, message_ids: Iterable[str]) -> OutboxReconciliationReport:
        findings: list[OutboxReconciliationFinding] = []
        checked_ids: set[str] = set()
        for message_id in message_ids:
            mid = str(message_id)
            checked_ids.add(mid)
            message = self._store.get(tenant_id=tenant_id, message_id=mid)
            backend_record = self._backend.get_record(tenant_id=tenant_id, message_id=mid)
            findings.extend(
                self._compare(
                    tenant_id=str(tenant_id),
                    message_id=mid,
                    message=message,
                    backend_record=backend_record,
                )
            )
        return OutboxReconciliationReport(
            tenant_id=str(tenant_id),
            checked=len(checked_ids),
            findings=tuple(findings),
        )

    def reconcile_claimable_window(self, *, tenant_id: str, limit: int = 100) -> OutboxReconciliationReport:
        checked_ids: list[str] = []
        for message in self._store.list_claimable(tenant_id=tenant_id, limit=limit):
            checked_ids.append(message.message_id)
        for record in self._backend.list_records(tenant_id=tenant_id, limit=limit):
            checked_ids.append(record.receipt.message_id)
        ordered_unique_ids = tuple(dict.fromkeys(checked_ids))
        return self.reconcile_messages(tenant_id=tenant_id, message_ids=ordered_unique_ids)

    def _compare(
        self,
        *,
        tenant_id: str,
        message_id: str,
        message: OutboxMessage | None,
        backend_record: OutboxDeliveryRecord | None,
    ) -> list[OutboxReconciliationFinding]:
        findings: list[OutboxReconciliationFinding] = []

        if message is None and backend_record is not None:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="backend_delivery_without_store_record",
                    detail="backend contains delivery evidence but outbox store record is missing",
                )
            )
            return findings

        if message is None:
            return findings

        if backend_record is None and message.state is OutboxState.DELIVERED:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="store_delivered_without_backend_receipt",
                    detail="outbox store says delivered but backend has no delivery receipt",
                )
            )
            return findings

        if backend_record is None:
            return findings

        if message.state in {OutboxState.PENDING, OutboxState.DELIVERING}:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="warning",
                    code="backend_delivered_but_store_not_finalized",
                    detail=f"backend delivery evidence exists while store state is {message.state.value}",
                )
            )

        if message.state is OutboxState.DEAD:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="dead_lettered_but_backend_delivered",
                    detail="message is dead-lettered in store but backend has a delivery receipt",
                )
            )

        if backend_record.topic != message.topic:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="topic_mismatch",
                    detail=f"store topic={message.topic!r} backend topic={backend_record.topic!r}",
                )
            )

        if backend_record.dedupe_key != message.dedupe_key:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="dedupe_key_mismatch",
                    detail="store dedupe_key does not match backend dedupe_key",
                )
            )

        backend_digest = str(backend_record.receipt.payload_digest or "").strip()
        expected_digest = _payload_digest(message.payload) if message.payload else ""
        if message.payload and not backend_digest:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="warning",
                    code="backend_payload_digest_missing",
                    detail="backend record has no payload digest for a non-empty payload",
                )
            )
        elif expected_digest and backend_digest and expected_digest != backend_digest:
            findings.append(
                OutboxReconciliationFinding(
                    tenant_id=tenant_id,
                    message_id=message_id,
                    severity="error",
                    code="payload_digest_mismatch",
                    detail="backend payload digest does not match canonical outbox payload",
                )
            )

        return findings


__all__ = [
    "CANON_OUTBOX_RECONCILIATION",
    "OutboxReconciliation",
    "OutboxReconciliationFinding",
    "OutboxReconciliationReport",
]
