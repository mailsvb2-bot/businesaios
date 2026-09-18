from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.messaging_event_identity import MESSAGE_SCHEMA_VERSION, MessageDirection, MessageIdentity
from reliability.idempotency_contract import IdempotencyStore

MESSAGE_RECORDED = "message.recorded"
MESSAGE_ARCHIVED = "message.archived"
MESSAGE_FACT_TYPES = frozenset({MESSAGE_RECORDED, MESSAGE_ARCHIVED})
CANON_MESSAGE_LIFECYCLE_OWNER = True


class MessageLifecycleStatus(str, Enum):
    RECORDED = "recorded"
    ARCHIVED = "archived"


class MessageNotFound(LookupError):
    pass


class MessageHistoryInvariantViolation(RuntimeError):
    pass


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def message_entity_id_for(*, identity: MessageIdentity, business_id: str) -> str:
    business = _required(business_id or identity.business_id, "business_id")
    raw = "\0".join(
        (
            identity.tenant_id,
            business,
            identity.direction.value,
            identity.channel,
            identity.message_id,
        )
    )
    return f"message:{_digest(raw)[:32]}"


@dataclass(frozen=True)
class Message:
    message_id: str
    tenant_id: str
    business_id: str
    channel: str
    direction: MessageDirection
    identity_digest: str
    customer_id: str | None = None
    conversation_id: str | None = None
    lifecycle_status: MessageLifecycleStatus = MessageLifecycleStatus.RECORDED
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None


class MessageProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, message_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in MESSAGE_FACT_TYPES:
                continue
            if str(event.get("source") or "") != "message_registry":
                raise MessageHistoryInvariantViolation("message fact has noncanonical source")
            if message_id is not None and entity_id != str(message_id):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (int(row["append_order"]), str(row["fact_id"])))
        return rows

    @staticmethod
    def _schema(payload: dict[str, object]) -> None:
        if payload.get("schema_version") != MESSAGE_SCHEMA_VERSION:
            raise MessageHistoryInvariantViolation("message history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, message_id: str) -> Message:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, message_id=message_id)
        if not facts:
            raise MessageNotFound(f"message not found: {message_id}")
        created_rows = [row for row in facts if row["fact_type"] == MESSAGE_RECORDED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise MessageHistoryInvariantViolation("message history must begin with exactly one record fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._schema(payload)
        digest = _required(payload.get("identity_digest"), "identity_digest")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise MessageHistoryInvariantViolation("message identity digest is invalid")
        message = Message(
            message_id=str(message_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            channel=_required(payload.get("channel"), "channel").lower(),
            direction=MessageDirection(_required(payload.get("direction"), "direction")),
            identity_digest=digest,
            customer_id=str(payload.get("customer_id") or "").strip() or None,
            conversation_id=str(payload.get("conversation_id") or "").strip() or None,
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if message.lifecycle_status is MessageLifecycleStatus.ARCHIVED:
                raise MessageHistoryInvariantViolation("message history continues after archive")
            payload = dict(row["payload"])
            self._schema(payload)
            if row["fact_type"] != MESSAGE_ARCHIVED:
                raise MessageHistoryInvariantViolation("unsupported message lifecycle fact")
            when = int(row["event_time_ms"])
            message = replace(
                message,
                lifecycle_status=MessageLifecycleStatus.ARCHIVED,
                updated_at_ms=max(message.updated_at_ms, when),
                archived_at_ms=when,
            )
        return message

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Message, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, message_id=value) for value in ids)


class MessageRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = MessageProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="message_fact",
            source="message_registry",
            id_prefix="message",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        when = int(time.time() * 1000) if value is None else int(value)
        if when < 0:
            raise ValueError("message timestamp cannot be negative")
        return when

    @staticmethod
    def _payload(*, identity: MessageIdentity, customer_id: str | None, conversation_id: str | None) -> dict[str, object]:
        customer = str(customer_id or "").strip() or None
        conversation = str(conversation_id or "").strip() or None
        if conversation and not customer:
            raise ValueError("conversation_id requires customer_id")
        return {
            "schema_version": MESSAGE_SCHEMA_VERSION,
            "direction": identity.direction.value,
            "channel": identity.channel,
            "identity_digest": _digest(identity.message_id),
            "customer_id": customer,
            "conversation_id": conversation,
        }

    @staticmethod
    def _state_token(message: Message) -> str:
        return "|".join(
            (
                message.lifecycle_status.value,
                str(message.updated_at_ms),
                message.direction.value,
                message.channel,
                message.identity_digest,
                message.customer_id or "",
                message.conversation_id or "",
            )
        )

    def record(
        self,
        *,
        identity: MessageIdentity,
        business_id: str | None = None,
        customer_id: str | None = None,
        conversation_id: str | None = None,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Message:
        tenant = _required(identity.tenant_id, "tenant_id")
        business = _required(business_id or identity.business_id, "business_id")
        if identity.business_id and identity.business_id != business:
            raise ValueError("message business scope mismatch")
        message_id = message_entity_id_for(identity=identity, business_id=business)
        payload = self._payload(identity=identity, customer_id=customer_id, conversation_id=conversation_id)
        try:
            current = self._projector.get(tenant_id=tenant, business_id=business, message_id=message_id)
        except MessageNotFound:
            current = None
        if current is not None:
            current_payload = {
                "schema_version": MESSAGE_SCHEMA_VERSION,
                "direction": current.direction.value,
                "channel": current.channel,
                "identity_digest": current.identity_digest,
                "customer_id": current.customer_id,
                "conversation_id": current.conversation_id,
            }
            if current_payload != payload:
                raise ValueError("message identity metadata cannot be rewritten")
            self._writer.repair_existing(
                tenant_id=tenant,
                business_id=business,
                entity_id=message_id,
                operation="record",
                idempotency_key=f"record:{message_id}",
                fact_type=MESSAGE_RECORDED,
                payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant,
            business_id=business,
            entity_id=message_id,
            operation="record",
            idempotency_key=f"record:{message_id}",
            fact_type=MESSAGE_RECORDED,
            payload=payload,
            occurred_at_ms=self._time(occurred_at_ms),
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant, business_id=business, message_id=message_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        message_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Message:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, message_id=message_id)
        if current.lifecycle_status is MessageLifecycleStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=message_id,
                operation="archive",
                idempotency_key=idempotency_key,
                fact_type=MESSAGE_ARCHIVED,
                payload={"schema_version": MESSAGE_SCHEMA_VERSION},
                event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=message_id,
            expected_state_token=self._state_token(current),
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=MESSAGE_ARCHIVED,
            payload={"schema_version": MESSAGE_SCHEMA_VERSION},
            occurred_at_ms=when,
            event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, message_id=message_id)

    def get(self, *, tenant_id: str, business_id: str, message_id: str) -> Message:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, message_id=message_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Message, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_MESSAGE_LIFECYCLE_OWNER",
    "MESSAGE_ARCHIVED",
    "MESSAGE_FACT_TYPES",
    "MESSAGE_RECORDED",
    "Message",
    "MessageHistoryInvariantViolation",
    "MessageLifecycleStatus",
    "MessageNotFound",
    "MessageProjector",
    "MessageRegistry",
    "message_entity_id_for",
]
