from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Protocol
import hashlib
import json
import threading

from core.tenancy.normalization import require_tenant_id


CANON_OUTBOX_STORE = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported json value: {type(value)!r}")


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class OutboxState(str, Enum):
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    DEAD = "dead"


class OutboxStoreConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OutboxMessage:
    tenant_id: str
    message_id: str
    topic: str
    dedupe_key: str
    payload: Mapping[str, Any]
    state: OutboxState = OutboxState.PENDING
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    available_at: datetime = field(default_factory=utc_now)
    claim_owner_id: str | None = None
    claim_expires_at: datetime | None = None
    delivery_attempts: int = 0
    last_error: str | None = None
    trace_id: str | None = None
    run_id: str | None = None
    decision_id: str | None = None
    payload_digest: str | None = None
    effect_key: str | None = None
    effect_kind: str | None = None
    backend_name: str | None = None
    external_id: str | None = None
    delivered_at: datetime | None = None
    delivery_metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.message_id or "").strip():
            raise ValueError("message_id is required")
        if not str(self.topic or "").strip():
            raise ValueError("topic is required")
        if not str(self.dedupe_key or "").strip():
            raise ValueError("dedupe_key is required")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None or self.available_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.claim_expires_at is not None and self.claim_expires_at.tzinfo is None:
            raise ValueError("claim_expires_at must be timezone-aware")
        if self.delivered_at is not None and self.delivered_at.tzinfo is None:
            raise ValueError("delivered_at must be timezone-aware")
        if int(self.delivery_attempts) < 0:
            raise ValueError("delivery_attempts must be >= 0")
        if self.payload_digest is not None and not str(self.payload_digest).strip():
            raise ValueError("payload_digest must not be blank when provided")
        if not isinstance(self.delivery_metadata, Mapping):
            raise ValueError("delivery_metadata must be a mapping")

    @property
    def resolved_payload_digest(self) -> str:
        digest = str(self.payload_digest or "").strip()
        return digest or canonical_payload_digest(self.payload)

    def semantically_matches(self, other: "OutboxMessage") -> bool:
        return (
            self.tenant_id == other.tenant_id
            and self.topic == other.topic
            and self.dedupe_key == other.dedupe_key
            and self.resolved_payload_digest == other.resolved_payload_digest
        )

    def with_delivery_receipt(
        self,
        *,
        backend_name: str | None,
        external_id: str | None,
        delivered_at: datetime | None = None,
        payload_digest: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OutboxMessage":
        return replace(
            self,
            state=OutboxState.DELIVERED,
            updated_at=delivered_at or utc_now(),
            delivered_at=delivered_at or utc_now(),
            claim_owner_id=None,
            claim_expires_at=None,
            last_error=None,
            backend_name=None if backend_name is None else str(backend_name),
            external_id=None if external_id is None else str(external_id),
            payload_digest=str(payload_digest or self.resolved_payload_digest),
            delivery_metadata=dict(metadata or {}),
        )

    def is_claim_expired(self, *, now: datetime | None = None) -> bool:
        if self.claim_expires_at is None:
            return False
        return (now or utc_now()) >= self.claim_expires_at

    def is_claimable(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        if self.state in {OutboxState.DEAD, OutboxState.DELIVERED}:
            return False
        if moment < self.available_at:
            return False
        if self.state is OutboxState.PENDING:
            return True
        return self.state is OutboxState.DELIVERING and self.is_claim_expired(now=moment)


class OutboxStore(Protocol):
    def enqueue(self, message: OutboxMessage) -> OutboxMessage: ...
    def get(self, *, tenant_id: str, message_id: str) -> OutboxMessage | None: ...
    def get_by_dedupe_key(self, *, tenant_id: str, dedupe_key: str) -> OutboxMessage | None: ...
    def list_claimable(self, *, tenant_id: str, limit: int = 100, now: datetime | None = None) -> tuple[OutboxMessage, ...]: ...
    def list_claimable_all(self, *, limit: int = 100, now: datetime | None = None) -> tuple[OutboxMessage, ...]: ...
    def claim(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        claim_ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> OutboxMessage | None: ...
    def mark_delivered(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        now: datetime | None = None,
        backend_name: str | None = None,
        external_id: str | None = None,
        payload_digest: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OutboxMessage: ...
    def schedule_retry(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        delay_seconds: int,
        error: str,
        now: datetime | None = None,
    ) -> OutboxMessage: ...
    def move_to_dead_letter(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        error: str,
        now: datetime | None = None,
    ) -> OutboxMessage: ...


class InMemoryOutboxStore(OutboxStore):
    def __init__(self) -> None:
        self._messages: dict[tuple[str, str], OutboxMessage] = {}
        self._by_dedupe: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    def enqueue(self, message: OutboxMessage) -> OutboxMessage:
        message = replace(message, payload_digest=message.resolved_payload_digest)
        message.validate()
        message_key = (message.tenant_id, message.message_id)
        dedupe_key = (message.tenant_id, message.dedupe_key)
        with self._lock:
            existing_id = self._by_dedupe.get(dedupe_key)
            if existing_id is not None:
                existing = self._messages[(message.tenant_id, existing_id)]
                self._assert_semantic_match(existing=existing, incoming=message, on='dedupe_key')
                return existing
            existing = self._messages.get(message_key)
            if existing is not None:
                self._assert_semantic_match(existing=existing, incoming=message, on='message_id')
                return existing
            self._messages[message_key] = message
            self._by_dedupe[dedupe_key] = message.message_id
            return message

    def get(self, *, tenant_id: str, message_id: str) -> OutboxMessage | None:
        with self._lock:
            return self._messages.get((require_tenant_id(tenant_id), str(message_id)))

    def get_by_dedupe_key(self, *, tenant_id: str, dedupe_key: str) -> OutboxMessage | None:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            existing_id = self._by_dedupe.get((tid, str(dedupe_key)))
            if existing_id is None:
                return None
            return self._messages.get((tid, existing_id))

    def list_claimable(self, *, tenant_id: str, limit: int = 100, now: datetime | None = None) -> tuple[OutboxMessage, ...]:
        tid = require_tenant_id(tenant_id)
        moment = now or utc_now()
        with self._lock:
            items = [
                item
                for (item_tid, _), item in self._messages.items()
                if item_tid == tid and item.is_claimable(now=moment)
            ]
        items.sort(key=lambda item: (item.available_at, item.created_at, item.message_id))
        return tuple(items[: max(1, int(limit))])

    def list_claimable_all(self, *, limit: int = 100, now: datetime | None = None) -> tuple[OutboxMessage, ...]:
        moment = now or utc_now()
        with self._lock:
            items = [item for item in self._messages.values() if item.is_claimable(now=moment)]
        items.sort(key=lambda item: (item.available_at, item.created_at, item.tenant_id, item.message_id))
        return tuple(items[: max(1, int(limit))])

    def claim(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        claim_ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> OutboxMessage | None:
        owner = str(owner_id).strip()
        if not owner:
            raise ValueError("owner_id is required")
        moment = now or utc_now()
        with self._lock:
            message = self._require(tenant_id=tenant_id, message_id=message_id)
            if not message.is_claimable(now=moment):
                return None
            claimed = replace(
                message,
                state=OutboxState.DELIVERING,
                updated_at=moment,
                claim_owner_id=owner,
                claim_expires_at=moment + timedelta(seconds=max(1, int(claim_ttl_seconds))),
                delivery_attempts=int(message.delivery_attempts) + 1,
            )
            self._messages[(claimed.tenant_id, claimed.message_id)] = claimed
            return claimed

    def mark_delivered(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        now: datetime | None = None,
        backend_name: str | None = None,
        external_id: str | None = None,
        payload_digest: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OutboxMessage:
        with self._lock:
            message = self._require_owned(tenant_id=tenant_id, message_id=message_id, owner_id=owner_id)
            delivered_at = now or utc_now()
            updated = message.with_delivery_receipt(
                backend_name=backend_name,
                external_id=external_id,
                delivered_at=delivered_at,
                payload_digest=payload_digest,
                metadata=metadata,
            )
            self._messages[(updated.tenant_id, updated.message_id)] = updated
            return updated

    def schedule_retry(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        delay_seconds: int,
        error: str,
        now: datetime | None = None,
    ) -> OutboxMessage:
        moment = now or utc_now()
        with self._lock:
            message = self._require_owned(tenant_id=tenant_id, message_id=message_id, owner_id=owner_id)
            updated = replace(
                message,
                state=OutboxState.PENDING,
                updated_at=moment,
                available_at=moment + timedelta(seconds=max(1, int(delay_seconds))),
                claim_owner_id=None,
                claim_expires_at=None,
                last_error=str(error),
            )
            self._messages[(updated.tenant_id, updated.message_id)] = updated
            return updated

    def move_to_dead_letter(
        self,
        *,
        tenant_id: str,
        message_id: str,
        owner_id: str,
        error: str,
        now: datetime | None = None,
    ) -> OutboxMessage:
        with self._lock:
            message = self._require_owned(tenant_id=tenant_id, message_id=message_id, owner_id=owner_id)
            updated = replace(
                message,
                state=OutboxState.DEAD,
                updated_at=now or utc_now(),
                claim_owner_id=None,
                claim_expires_at=None,
                last_error=str(error),
            )
            self._messages[(updated.tenant_id, updated.message_id)] = updated
            return updated

    def _assert_semantic_match(self, *, existing: OutboxMessage, incoming: OutboxMessage, on: str) -> None:
        if existing.topic != incoming.topic:
            raise OutboxStoreConflict(f"outbox {on} conflict: topic drift")
        if existing.resolved_payload_digest != incoming.resolved_payload_digest:
            raise OutboxStoreConflict(f"outbox {on} conflict: payload drift")

    def _require(self, *, tenant_id: str, message_id: str) -> OutboxMessage:
        message = self._messages.get((require_tenant_id(tenant_id), str(message_id)))
        if message is None:
            raise KeyError(f"outbox message not found: {tenant_id}:{message_id}")
        return message

    def _require_owned(self, *, tenant_id: str, message_id: str, owner_id: str) -> OutboxMessage:
        message = self._require(tenant_id=tenant_id, message_id=message_id)
        if str(message.claim_owner_id or "") != str(owner_id):
            raise PermissionError("outbox ownership mismatch")
        if message.state is not OutboxState.DELIVERING:
            raise RuntimeError("outbox message is not in delivering state")
        return message


__all__ = [
    "CANON_OUTBOX_STORE",
    "InMemoryOutboxStore",
    "OutboxMessage",
    "OutboxState",
    "OutboxStore",
    "OutboxStoreConflict",
    "canonical_payload_digest",
    "utc_now",
]
