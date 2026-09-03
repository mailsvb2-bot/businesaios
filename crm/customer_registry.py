from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from typing import Any
from uuid import uuid4

from contracts.customer import (
    Customer,
    CustomerIdentity,
    CustomerIdentityBusy,
    CustomerIdentityConflict,
    CustomerIdentityStatus,
    CustomerIdentityUnavailable,
    CustomerNotFound,
    CustomerRecord,
    CustomerStatus,
    normalize_customer_optional_text,
    normalize_customer_subject,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyStore
from reliability.idempotency_scope import build_idempotency_key
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import SecretVault

CANON_CUSTOMER_REGISTRY = True
_CUSTOMER_CREATED = "customer.created"
_IDENTITY_ATTACHED = "customer.identity.attached"
_CONTACT_OBSERVED = "customer.contact.observed"
_CUSTOMER_ARCHIVED = "customer.archived"
_IDENTITY_SECRET_CONNECTOR = "customer_identity"


def _now_ms(value: int | None = None) -> int:
    return int(time.time() * 1000) if value is None else max(0, int(value))


def _identity_digest(*, tenant_id: str, business_id: str, channel: str, subject: str) -> str:
    raw = f"{tenant_id}\0{business_id}\0{channel}\0{subject}".encode()
    return hashlib.sha256(raw).hexdigest()


class CustomerRegistry:
    """Canonical Customer owner backed by EventStore, idempotency claims and encrypted PII vault."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore, pii_vault: SecretVault) -> None:
        self._events = event_store
        self._claims = idempotency_store
        self._pii = pii_vault

    @staticmethod
    def _identity_ref(*, tenant_id: str, business_id: str, identity_id: str) -> SecretRef:
        return SecretRef(
            tenant_id=str(tenant_id), connector_id=_IDENTITY_SECRET_CONNECTOR,
            scope=str(business_id), secret_name=str(identity_id),
        )

    def _write_identity_pii(
        self, *, tenant_id: str, business_id: str, identity_id: str, channel: str,
        subject_digest: str, external_subject: str, username: str | None, display_name: str | None,
    ) -> None:
        username = normalize_customer_optional_text(username, "username")
        display_name = normalize_customer_optional_text(display_name, "display_name")
        ref = self._identity_ref(tenant_id=tenant_id, business_id=business_id, identity_id=identity_id)
        plaintext = json.dumps(
            {
                "schema_version": 1,
                "external_subject": external_subject,
                "username": username,
                "display_name": display_name,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._pii.put(
            SecretRecord(
                ref=ref,
                ciphertext=b"pending",
                source=SecretSource.VAULT,
                metadata={
                    "kind": "customer_identity_pii",
                    "business_id": str(business_id),
                    "channel": str(channel),
                    "subject_digest": str(subject_digest),
                },
            ),
            plaintext=plaintext,
        )

    def _read_identity_pii(
        self, *, tenant_id: str, business_id: str, identity_id: str, channel: str, subject_digest: str,
    ) -> tuple[str, str | None, str | None]:
        ref = self._identity_ref(tenant_id=tenant_id, business_id=business_id, identity_id=identity_id)
        try:
            raw = json.loads(self._pii.get(ref).decode("utf-8"))
        except (KeyError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CustomerIdentityUnavailable("customer identity PII is unavailable") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise CustomerIdentityUnavailable("customer identity PII version is invalid")
        normalized_channel, subject = normalize_customer_subject(channel, raw.get("external_subject"))
        actual_digest = _identity_digest(
            tenant_id=tenant_id, business_id=business_id, channel=normalized_channel, subject=subject,
        )
        if normalized_channel != channel or actual_digest != subject_digest:
            raise CustomerIdentityUnavailable("customer identity PII does not match canonical digest")
        username = None if raw.get("username") is None else str(raw.get("username"))
        display_name = None if raw.get("display_name") is None else str(raw.get("display_name"))
        return subject, username, display_name

    def _facts(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            if not fact_type.startswith("customer."):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": str(envelope.get("entity_id") or ""),
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
                "correlation_id": event.get("correlation_id"),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def _append_fact_once(
        self, *, tenant_id: str, business_id: str, customer_id: str, fact_id: str,
        fact_type: str, payload: dict[str, Any], occurred_at_ms: int, correlation_id: str | None = None,
    ) -> None:
        if any(row["fact_id"] == fact_id for row in self._facts(tenant_id=tenant_id, business_id=business_id)):
            return
        key = build_idempotency_key(
            tenant_id=tenant_id, namespace="customer_fact", operation="append", key=fact_id,
            semantic_scope={"business_id": business_id, "customer_id": customer_id, "fact_type": fact_type},
        )
        owner_id = f"customer-fact:{uuid4()}"
        decision = self._claims.reserve(key=key, owner_id=owner_id, lease_ttl_seconds=300)
        if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
            return
        if decision.resolution is IdempotencyResolution.REJECTED_IN_PROGRESS:
            raise CustomerIdentityBusy("customer fact append is already in progress")
        if decision.resolution is not IdempotencyResolution.ACCEPTED:
            raise CustomerIdentityConflict(f"customer fact append rejected: {decision.resolution.value}")
        if any(row["fact_id"] == fact_id for row in self._facts(tenant_id=tenant_id, business_id=business_id)):
            self._claims.mark_completed(key=key, owner_id=owner_id, result_ref=fact_id)
            return
        self._events.append_event(BusinessFactV1(
            fact_id=fact_id, tenant_id=tenant_id, business_id=business_id, fact_type=fact_type,
            entity_id=customer_id, event_time_ms=occurred_at_ms, observed_at_ms=occurred_at_ms,
            source="customer_registry", payload=payload, correlation_id=correlation_id,
        ).as_event())
        self._claims.mark_completed(key=key, owner_id=owner_id, result_ref=fact_id)

    def _project(self, *, tenant_id: str, business_id: str, customer_id: str) -> CustomerRecord:
        facts = [row for row in self._facts(tenant_id=tenant_id, business_id=business_id) if row["entity_id"] == customer_id]
        created = next((row for row in facts if row["fact_type"] == _CUSTOMER_CREATED), None)
        if created is None:
            raise CustomerNotFound("customer was not found in the active business")
        customer = Customer(
            customer_id=customer_id, tenant_id=tenant_id, business_id=business_id,
            display_name=None, created_at_ms=created["event_time_ms"],
            updated_at_ms=created["event_time_ms"], first_seen_at=created["event_time_ms"],
        )
        identities: dict[str, CustomerIdentity] = {}
        for row in facts:
            payload = row["payload"]
            if row["fact_type"] == _IDENTITY_ATTACHED:
                identity_id = str(payload.get("identity_id") or "")
                channel = str(payload.get("channel") or "")
                subject_digest = str(payload.get("subject_digest") or "")
                subject, username, display_name = self._read_identity_pii(
                    tenant_id=tenant_id, business_id=business_id, identity_id=identity_id,
                    channel=channel, subject_digest=subject_digest,
                )
                identity = CustomerIdentity(
                    identity_id=identity_id, tenant_id=tenant_id,
                    business_id=business_id, customer_id=customer_id, channel=channel,
                    external_subject=subject, username=username, display_name=display_name,
                    created_at_ms=row["event_time_ms"], updated_at_ms=row["event_time_ms"],
                    first_contact_at_ms=payload.get("first_contact_at_ms"),
                    last_contact_at_ms=payload.get("last_contact_at_ms"),
                )
                identities[identity.identity_id] = identity
                customer = replace(
                    customer,
                    display_name=customer.display_name or identity.display_name,
                    updated_at_ms=max(customer.updated_at_ms, row["event_time_ms"]),
                )
            elif row["fact_type"] == _CONTACT_OBSERVED:
                identity_id = str(payload.get("identity_id") or "")
                identity = identities.get(identity_id)
                if identity is not None:
                    first = identity.first_contact_at_ms if identity.first_contact_at_ms is not None else row["event_time_ms"]
                    identities[identity_id] = replace(
                        identity,
                        first_contact_at_ms=min(first, row["event_time_ms"]),
                        last_contact_at_ms=max(identity.last_contact_at_ms or 0, row["event_time_ms"]),
                        updated_at_ms=max(identity.updated_at_ms, row["event_time_ms"]),
                    )
                    customer = replace(customer, updated_at_ms=max(customer.updated_at_ms, row["event_time_ms"]))
            elif row["fact_type"] == _CUSTOMER_ARCHIVED:
                customer = replace(
                    customer, status=CustomerStatus.ARCHIVED,
                    archived_at_ms=row["event_time_ms"], updated_at_ms=max(customer.updated_at_ms, row["event_time_ms"]),
                )
                identities = {
                    key: replace(
                        value, status=CustomerIdentityStatus.REVOKED,
                        revoked_at_ms=row["event_time_ms"], updated_at_ms=max(value.updated_at_ms, row["event_time_ms"]),
                    )
                    for key, value in identities.items()
                }
        return CustomerRecord(
            customer=customer,
            identities=tuple(sorted(identities.values(), key=lambda item: (item.created_at_ms, item.identity_id))),
        )

    def get_customer(self, *, tenant_id: str, business_id: str, customer_id: str) -> CustomerRecord:
        return self._project(
            tenant_id=str(tenant_id).strip(), business_id=str(business_id).strip(), customer_id=str(customer_id).strip(),
        )

    def list_customers(self, *, tenant_id: str, business_id: str, include_archived: bool = False) -> tuple[Customer, ...]:
        ids = sorted({
            row["entity_id"] for row in self._facts(tenant_id=tenant_id, business_id=business_id)
            if row["fact_type"] == _CUSTOMER_CREATED
        })
        records = tuple(
            self._project(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)
            for customer_id in ids
        )
        return tuple(
            record.customer for record in records
            if include_archived or record.customer.status is CustomerStatus.ACTIVE
        )

    def find_by_identity(self, *, tenant_id: str, business_id: str, channel: str, external_subject: str) -> CustomerRecord:
        tenant_id, business_id = str(tenant_id).strip(), str(business_id).strip()
        channel, subject = normalize_customer_subject(channel, external_subject)
        digest = _identity_digest(tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject)
        for row in self._facts(tenant_id=tenant_id, business_id=business_id):
            if row["fact_type"] != _IDENTITY_ATTACHED:
                continue
            payload = row["payload"]
            if payload.get("channel") == channel and payload.get("subject_digest") == digest:
                return self._project(tenant_id=tenant_id, business_id=business_id, customer_id=row["entity_id"])
        raise CustomerNotFound("customer identity was not found in the active business")

    def _claim_identity(
        self, *, tenant_id: str, business_id: str, channel: str, subject: str, requested_customer_id: str | None,
    ) -> tuple[str, Any, str, str]:
        digest = _identity_digest(tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject)
        key = build_idempotency_key(
            tenant_id=tenant_id, namespace="customer_identity", operation="claim", key=digest,
            semantic_scope={"business_id": business_id, "channel": channel, "subject_digest": digest},
        )
        existing = self._claims.get(key=key)
        recorded_customer = str((existing.metadata if existing else {}).get("customer_id") or "").strip()
        requested = str(requested_customer_id or "").strip()
        if requested and recorded_customer and requested != recorded_customer:
            raise CustomerIdentityConflict("identity already belongs to another customer in this business")
        customer_id = requested or recorded_customer or str(uuid4())
        owner_id = f"customer-registry:{uuid4()}"
        decision = self._claims.reserve(
            key=key, owner_id=owner_id, lease_ttl_seconds=300,
            metadata_patch={"customer_id": customer_id, "business_id": business_id, "channel": channel},
        )
        if decision.resolution is IdempotencyResolution.ACCEPTED:
            return customer_id, key, owner_id, digest
        claim_customer = str(decision.replay_result_ref or decision.record.metadata.get("customer_id") or "").strip()
        if requested and claim_customer and claim_customer != requested:
            raise CustomerIdentityConflict("identity already belongs to another customer in this business")
        if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED and claim_customer:
            return claim_customer, key, "", digest
        if decision.resolution is IdempotencyResolution.REJECTED_IN_PROGRESS:
            raise CustomerIdentityBusy("customer identity claim is already in progress")
        raise CustomerIdentityConflict(f"customer identity claim rejected: {decision.resolution.value}")

    def ensure_customer_identity(
        self, *, tenant_id: str, business_id: str, channel: str, external_subject: str,
        username: str | None = None, display_name: str | None = None, occurred_at_ms: int | None = None,
        correlation_id: str | None = None,
    ) -> CustomerRecord:
        tenant_id, business_id = str(tenant_id).strip(), str(business_id).strip()
        channel, subject = normalize_customer_subject(channel, external_subject)
        try:
            existing = self.find_by_identity(
                tenant_id=tenant_id, business_id=business_id, channel=channel, external_subject=subject,
            )
        except CustomerNotFound:
            existing = None
        if existing is not None:
            if existing.customer.status is not CustomerStatus.ACTIVE:
                raise CustomerIdentityConflict("archived customer identity cannot receive new ingress")
            identity = next(
                item for item in existing.identities
                if item.channel == channel and item.external_subject == subject
            )
            if username is not None or display_name is not None:
                digest = _identity_digest(
                    tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject,
                )
                self._write_identity_pii(
                    tenant_id=tenant_id, business_id=business_id, identity_id=identity.identity_id,
                    channel=channel, subject_digest=digest, external_subject=subject,
                    username=username if username is not None else identity.username,
                    display_name=display_name if display_name is not None else identity.display_name,
                )
                return self.get_customer(
                    tenant_id=tenant_id, business_id=business_id, customer_id=existing.customer.customer_id,
                )
            return existing
        customer_id, key, owner_id, digest = self._claim_identity(
            tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject, requested_customer_id=None,
        )
        if not owner_id:
            return self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)
        now = _now_ms(occurred_at_ms)
        identity_id = f"identity:{digest[:32]}"
        self._write_identity_pii(
            tenant_id=tenant_id, business_id=business_id, identity_id=identity_id,
            channel=channel, subject_digest=digest, external_subject=subject,
            username=username, display_name=display_name,
        )
        self._append_fact_once(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            fact_id=f"customer:{customer_id}:created", fact_type=_CUSTOMER_CREATED,
            payload={}, occurred_at_ms=now, correlation_id=correlation_id,
        )
        self._append_fact_once(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            fact_id=f"customer:{customer_id}:{identity_id}:attached", fact_type=_IDENTITY_ATTACHED,
            payload={
                "identity_id": identity_id,
                "channel": channel,
                "subject_digest": digest,
                "first_contact_at_ms": now,
                "last_contact_at_ms": now,
            },
            occurred_at_ms=now, correlation_id=correlation_id,
        )
        self._claims.mark_completed(
            key=key, owner_id=owner_id, result_ref=customer_id, metadata_patch={"customer_id": customer_id},
        )
        return self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)

    def attach_identity(
        self, *, tenant_id: str, business_id: str, customer_id: str, channel: str, external_subject: str,
        username: str | None = None, display_name: str | None = None, occurred_at_ms: int | None = None,
        correlation_id: str | None = None,
    ) -> CustomerIdentity:
        tenant_id, business_id, customer_id = str(tenant_id).strip(), str(business_id).strip(), str(customer_id).strip()
        record = self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)
        if record.customer.status is not CustomerStatus.ACTIVE:
            raise CustomerIdentityConflict("cannot attach identity to archived customer")
        channel, subject = normalize_customer_subject(channel, external_subject)
        try:
            existing = self.find_by_identity(
                tenant_id=tenant_id, business_id=business_id, channel=channel, external_subject=subject,
            )
        except CustomerNotFound:
            existing = None
        if existing is not None:
            if existing.customer.customer_id != customer_id:
                raise CustomerIdentityConflict("identity already belongs to another customer in this business")
            return next(
                identity for identity in existing.identities
                if identity.channel == channel and identity.external_subject == subject
            )
        claimed_customer, key, owner_id, digest = self._claim_identity(
            tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject,
            requested_customer_id=customer_id,
        )
        if claimed_customer != customer_id:
            raise CustomerIdentityConflict("identity already belongs to another customer in this business")
        if not owner_id:
            return next(
                identity for identity in self.get_customer(
                    tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
                ).identities
                if identity.channel == channel and identity.external_subject == subject
            )
        now = _now_ms(occurred_at_ms)
        identity_id = f"identity:{digest[:32]}"
        self._write_identity_pii(
            tenant_id=tenant_id, business_id=business_id, identity_id=identity_id,
            channel=channel, subject_digest=digest, external_subject=subject,
            username=username, display_name=display_name,
        )
        self._append_fact_once(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            fact_id=f"customer:{customer_id}:{identity_id}:attached", fact_type=_IDENTITY_ATTACHED,
            payload={
                "identity_id": identity_id,
                "channel": channel,
                "subject_digest": digest,
                "first_contact_at_ms": now,
                "last_contact_at_ms": now,
            },
            occurred_at_ms=now, correlation_id=correlation_id,
        )
        self._claims.mark_completed(
            key=key, owner_id=owner_id, result_ref=customer_id, metadata_patch={"customer_id": customer_id},
        )
        return next(
            identity for identity in self.get_customer(
                tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            ).identities
            if identity.identity_id == identity_id
        )

    def record_contact(
        self, *, tenant_id: str, business_id: str, customer_id: str, channel: str, external_subject: str,
        contact_id: str, username: str | None = None, display_name: str | None = None,
        occurred_at_ms: int | None = None, correlation_id: str | None = None,
    ) -> CustomerRecord:
        tenant_id, business_id, customer_id = str(tenant_id).strip(), str(business_id).strip(), str(customer_id).strip()
        record = self.find_by_identity(
            tenant_id=tenant_id, business_id=business_id, channel=channel, external_subject=external_subject,
        )
        if record.customer.customer_id != customer_id:
            raise CustomerIdentityConflict("contact identity does not belong to customer")
        if record.customer.status is not CustomerStatus.ACTIVE:
            raise CustomerIdentityConflict("archived customer cannot receive contact")
        channel, subject = normalize_customer_subject(channel, external_subject)
        identity = next(
            item for item in record.identities
            if item.channel == channel and item.external_subject == subject
        )
        now = _now_ms(occurred_at_ms)
        if not str(contact_id or "").strip():
            raise ValueError("contact_id is required")
        contact_digest = hashlib.sha256(str(contact_id).strip().encode()).hexdigest()[:32]
        self._append_fact_once(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            fact_id=f"customer:{customer_id}:contact:{contact_digest}", fact_type=_CONTACT_OBSERVED,
            payload={"identity_id": identity.identity_id, "channel": channel},
            occurred_at_ms=now, correlation_id=correlation_id,
        )
        if username is not None or display_name is not None:
            digest = _identity_digest(
                tenant_id=tenant_id, business_id=business_id, channel=channel, subject=subject,
            )
            self._write_identity_pii(
                tenant_id=tenant_id, business_id=business_id, identity_id=identity.identity_id,
                channel=channel, subject_digest=digest, external_subject=subject,
                username=username if username is not None else identity.username,
                display_name=display_name if display_name is not None else identity.display_name,
            )
        return self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)

    def archive_customer(
        self, *, tenant_id: str, business_id: str, customer_id: str, occurred_at_ms: int | None = None,
    ) -> Customer:
        record = self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)
        if record.customer.status is CustomerStatus.ARCHIVED:
            return record.customer
        now = _now_ms(occurred_at_ms)
        self._append_fact_once(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
            fact_id=f"customer:{customer_id}:archived", fact_type=_CUSTOMER_ARCHIVED,
            payload={}, occurred_at_ms=now,
        )
        return self.get_customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        ).customer

    def revoke_customer_pii(self, *, tenant_id: str, business_id: str, customer_id: str) -> int:
        record = self.get_customer(tenant_id=tenant_id, business_id=business_id, customer_id=customer_id)
        deleted = 0
        for identity in record.identities:
            ref = self._identity_ref(
                tenant_id=tenant_id, business_id=business_id, identity_id=identity.identity_id,
            )
            try:
                self._pii.delete(ref)
            except KeyError:
                continue
            deleted += 1
        return deleted


__all__ = ["CANON_CUSTOMER_REGISTRY", "CustomerRegistry"]
