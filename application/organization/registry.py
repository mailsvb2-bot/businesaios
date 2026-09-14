from __future__ import annotations

import hashlib
import time
from typing import Any

from application.organization.facts import ORGANIZATION_ARCHIVED, ORGANIZATION_CREATED, ORGANIZATION_UPDATED
from application.organization.projector import OrganizationProjector
from contracts.event_store import BusinessFactV1
from contracts.organization import Organization, OrganizationStatus
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyStore
from reliability.idempotency_scope import build_idempotency_key

CANON_ORGANIZATION_LIFECYCLE_OWNER = True


def _now_ms(value: int | None) -> int:
    return int(time.time() * 1000) if value is None else max(0, int(value))


def _fact_id(*, tenant_id: str, business_id: str, organization_id: str, operation: str, idempotency_key: str) -> str:
    raw = "\0".join((tenant_id, business_id, organization_id, operation, idempotency_key)).encode("utf-8")
    return f"organization:{hashlib.sha256(raw).hexdigest()}"


class OrganizationRegistry:
    """Single Organization lifecycle writer backed by the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._events = event_store
        self._claims = idempotency_store
        self._projector = OrganizationProjector(event_store)

    def _append_once(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        operation: str,
        idempotency_key: str,
        fact_type: str,
        payload: dict[str, object],
        occurred_at_ms: int,
    ) -> None:
        normalized_key = str(idempotency_key or "").strip()
        if not normalized_key:
            raise ValueError("idempotency_key is required")
        fact_id = _fact_id(
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            organization_id=str(organization_id),
            operation=str(operation),
            idempotency_key=normalized_key,
        )
        scope = build_idempotency_key(
            tenant_id=str(tenant_id),
            namespace="organization_fact",
            operation=str(operation),
            key=normalized_key,
            semantic_scope={
                "business_id": str(business_id),
                "organization_id": str(organization_id),
                "payload": dict(payload),
            },
        )
        owner_id = f"organization-fact:{fact_id}"
        resolution = self._claims.reserve(key=scope, owner_id=owner_id, lease_ttl_seconds=300)
        if resolution.resolution is IdempotencyResolution.REPLAY_COMPLETED:
            return
        if resolution.resolution is not IdempotencyResolution.ACCEPTED:
            raise RuntimeError(f"organization mutation rejected: {resolution.resolution.value}")
        self._events.append_event(
            BusinessFactV1(
                fact_id=fact_id,
                tenant_id=str(tenant_id),
                business_id=str(business_id),
                fact_type=str(fact_type),
                entity_id=str(organization_id),
                event_time_ms=int(occurred_at_ms),
                observed_at_ms=int(occurred_at_ms),
                source="organization_registry",
                payload=dict(payload),
            ).as_event()
        )
        self._claims.mark_completed(key=scope, owner_id=owner_id, result_ref=fact_id)

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        name: str | None = None,
        organization_type: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        when = _now_ms(occurred_at_ms)
        candidate = Organization(
            organization_id=organization_id,
            tenant_id=tenant_id,
            business_id=business_id,
            name=name,
            organization_type=organization_type,
            created_at_ms=when,
            updated_at_ms=when,
        )
        try:
            existing = self._projector.get(
                tenant_id=candidate.tenant_id,
                business_id=candidate.business_id,
                organization_id=candidate.organization_id,
            )
        except LookupError:
            existing = None
        if existing is not None:
            if existing.name != candidate.name or existing.organization_type != candidate.organization_type:
                raise ValueError("organization already exists with different identity metadata")
            return existing
        self._append_once(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            organization_id=candidate.organization_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_CREATED,
            payload={"name": candidate.name, "organization_type": candidate.organization_type},
            occurred_at_ms=when,
        )
        return self._projector.get(
            tenant_id=candidate.tenant_id,
            business_id=candidate.business_id,
            organization_id=candidate.organization_id,
        )

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        name: str | None = None,
        organization_type: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        if current.status is OrganizationStatus.ARCHIVED:
            raise ValueError("archived organization cannot be updated")
        when = max(current.updated_at_ms, _now_ms(occurred_at_ms))
        candidate = Organization(
            organization_id=current.organization_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            name=current.name if name is None else name,
            organization_type=current.organization_type if organization_type is None else organization_type,
            created_at_ms=current.created_at_ms,
            updated_at_ms=when,
        )
        if candidate.name == current.name and candidate.organization_type == current.organization_type:
            return current
        self._append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            organization_id=organization_id,
            operation="update",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_UPDATED,
            payload={"name": candidate.name, "organization_type": candidate.organization_type},
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        if current.status is OrganizationStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, _now_ms(occurred_at_ms))
        self._append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            organization_id=organization_id,
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_ARCHIVED,
            payload={},
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def get(self, *, tenant_id: str, business_id: str, organization_id: str) -> Organization:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Organization, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_ORGANIZATION_LIFECYCLE_OWNER", "OrganizationRegistry"]
