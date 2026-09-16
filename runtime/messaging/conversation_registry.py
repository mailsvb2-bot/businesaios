from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

CONVERSATION_SCHEMA_VERSION = 1
CONVERSATION_CREATED = "conversation.created"
CONVERSATION_ACTIVITY_OBSERVED = "conversation.activity.observed"
CONVERSATION_ARCHIVED = "conversation.archived"
CONVERSATION_FACT_TYPES = frozenset(
    {CONVERSATION_CREATED, CONVERSATION_ACTIVITY_OBSERVED, CONVERSATION_ARCHIVED}
)
CANON_CONVERSATION_LIFECYCLE_OWNER = True


class ConversationLifecycleStatus(str, Enum):
    OPEN = "open"
    ARCHIVED = "archived"


class ConversationNotFound(LookupError):
    pass


class ConversationHistoryInvariantViolation(RuntimeError):
    pass


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _route_digest(*, tenant_id: str, business_id: str, channel: str, route_ref: str) -> str:
    raw = "\0".join((tenant_id, business_id, channel, route_ref)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def conversation_id_for(*, tenant_id: str, business_id: str, channel: str, route_ref: str) -> str:
    tenant = _required(tenant_id, "tenant_id")
    business = _required(business_id, "business_id")
    normalized_channel = _required(channel, "channel").lower()
    route = _required(route_ref, "route_ref")
    return f"conversation:{_route_digest(tenant_id=tenant, business_id=business, channel=normalized_channel, route_ref=route)[:32]}"


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    tenant_id: str
    business_id: str
    customer_id: str
    channel: str
    route_digest: str
    lifecycle_status: ConversationLifecycleStatus = ConversationLifecycleStatus.OPEN
    created_at_ms: int = 0
    updated_at_ms: int = 0
    last_activity_at_ms: int | None = None
    activity_count: int = 0
    archived_at_ms: int | None = None


class ConversationProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, conversation_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in CONVERSATION_FACT_TYPES:
                continue
            if str(event.get("source") or "") != "conversation_registry":
                raise ConversationHistoryInvariantViolation("conversation fact has noncanonical source")
            if conversation_id is not None and entity_id != str(conversation_id):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (int(row["append_order"]), str(row["fact_id"])))
        return rows

    @staticmethod
    def _schema(payload: dict[str, object]) -> None:
        if payload.get("schema_version") != CONVERSATION_SCHEMA_VERSION:
            raise ConversationHistoryInvariantViolation("conversation history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, conversation_id: str) -> Conversation:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, conversation_id=conversation_id)
        if not facts:
            raise ConversationNotFound(f"conversation not found: {conversation_id}")
        created_rows = [row for row in facts if row["fact_type"] == CONVERSATION_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise ConversationHistoryInvariantViolation("conversation history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._schema(payload)
        route_digest = _required(payload.get("route_digest"), "route_digest")
        if len(route_digest) != 64 or any(ch not in "0123456789abcdef" for ch in route_digest):
            raise ConversationHistoryInvariantViolation("conversation route digest is invalid")
        conversation = Conversation(
            conversation_id=str(conversation_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            customer_id=_required(payload.get("customer_id"), "customer_id"),
            channel=_required(payload.get("channel"), "channel").lower(),
            route_digest=route_digest,
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if conversation.lifecycle_status is ConversationLifecycleStatus.ARCHIVED:
                raise ConversationHistoryInvariantViolation("conversation history continues after archive")
            payload = dict(row["payload"])
            self._schema(payload)
            when = int(row["event_time_ms"])
            if row["fact_type"] == CONVERSATION_ACTIVITY_OBSERVED:
                _required(payload.get("contact_digest"), "contact_digest")
                conversation = replace(
                    conversation,
                    updated_at_ms=max(conversation.updated_at_ms, when),
                    last_activity_at_ms=max(conversation.last_activity_at_ms or 0, when),
                    activity_count=conversation.activity_count + 1,
                )
            elif row["fact_type"] == CONVERSATION_ARCHIVED:
                conversation = replace(
                    conversation,
                    lifecycle_status=ConversationLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(conversation.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return conversation

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Conversation, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, conversation_id=value) for value in ids)


class ConversationRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore, customer_registry: Any) -> None:
        self._projector = ConversationProjector(event_store)
        self._customers = customer_registry
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="conversation_fact",
            source="conversation_registry",
            id_prefix="conversation",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def _assert_active_customer(self, *, tenant_id: str, business_id: str, customer_id: str) -> None:
        record = self._customers.get_customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id
        )
        if str(record.customer.customer_id) != customer_id:
            raise ValueError("conversation customer scope mismatch")
        if str(getattr(record.customer.status, "value", record.customer.status)) != "active":
            raise ValueError("conversation requires an active customer")

    @staticmethod
    def _state_token(conversation: Conversation) -> str:
        return "|".join((
            conversation.lifecycle_status.value,
            str(conversation.updated_at_ms),
            str(conversation.activity_count),
            conversation.customer_id,
            conversation.channel,
            conversation.route_digest,
        ))

    def ensure_ingress(
        self,
        *,
        tenant_id: str,
        business_id: str,
        customer_id: str,
        channel: str,
        route_ref: str,
        contact_id: str,
        occurred_at_ms: int | None = None,
    ) -> Conversation:
        tenant = _required(tenant_id, "tenant_id")
        business = _required(business_id, "business_id")
        customer = _required(customer_id, "customer_id")
        self._assert_active_customer(tenant_id=tenant, business_id=business, customer_id=customer)
        normalized_channel = _required(channel, "channel").lower()
        route = _required(route_ref, "route_ref")
        contact = _required(contact_id, "contact_id")
        conversation_id = conversation_id_for(
            tenant_id=tenant, business_id=business, channel=normalized_channel, route_ref=route
        )
        digest = _route_digest(
            tenant_id=tenant, business_id=business, channel=normalized_channel, route_ref=route
        )
        when = self._time(occurred_at_ms)
        create_payload: dict[str, object] = {
            "schema_version": CONVERSATION_SCHEMA_VERSION,
            "customer_id": customer,
            "channel": normalized_channel,
            "route_digest": digest,
        }
        try:
            current = self._projector.get(
                tenant_id=tenant, business_id=business, conversation_id=conversation_id
            )
        except ConversationNotFound:
            self._writer.append_once(
                tenant_id=tenant,
                business_id=business,
                entity_id=conversation_id,
                operation="create",
                idempotency_key=f"create:{conversation_id}",
                fact_type=CONVERSATION_CREATED,
                payload=create_payload,
                occurred_at_ms=when,
            )
            current = self._projector.get(
                tenant_id=tenant, business_id=business, conversation_id=conversation_id
            )
        if (
            current.customer_id != customer
            or current.channel != normalized_channel
            or current.route_digest != digest
        ):
            raise ValueError("conversation identity metadata cannot be rewritten")
        if current.lifecycle_status is ConversationLifecycleStatus.ARCHIVED:
            raise ValueError("archived conversation cannot receive ingress")
        contact_digest = hashlib.sha256(contact.encode("utf-8")).hexdigest()
        payload = {
            "schema_version": CONVERSATION_SCHEMA_VERSION,
            "contact_digest": contact_digest,
        }
        self._writer.append_transition_once(
            tenant_id=tenant,
            business_id=business,
            entity_id=conversation_id,
            expected_state_token=self._state_token(current),
            operation="observe_activity",
            idempotency_key=f"activity:{contact_digest}",
            fact_type=CONVERSATION_ACTIVITY_OBSERVED,
            payload=payload,
            occurred_at_ms=max(current.updated_at_ms, when),
        )
        return self._projector.get(
            tenant_id=tenant, business_id=business, conversation_id=conversation_id
        )

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        conversation_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Conversation:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, conversation_id=conversation_id
        )
        if current.lifecycle_status is ConversationLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=conversation_id,
            expected_state_token=self._state_token(current),
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=CONVERSATION_ARCHIVED,
            payload={"schema_version": CONVERSATION_SCHEMA_VERSION},
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, conversation_id=conversation_id
        )

    def get(self, *, tenant_id: str, business_id: str, conversation_id: str) -> Conversation:
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, conversation_id=conversation_id
        )

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Conversation, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_CONVERSATION_LIFECYCLE_OWNER",
    "CONVERSATION_SCHEMA_VERSION",
    "Conversation",
    "ConversationHistoryInvariantViolation",
    "ConversationLifecycleStatus",
    "ConversationNotFound",
    "ConversationProjector",
    "ConversationRegistry",
    "conversation_id_for",
]
