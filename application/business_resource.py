from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.asset import AssetProjector
from application.ontology import EventFactLifecycleWriter
from contracts.asset import AssetLifecycleStatus
from contracts.business_resource import (
    BUSINESS_RESOURCE_SCHEMA_VERSION,
    BusinessResource,
    BusinessResourceNotFound,
    ResourceLifecycleStatus,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

RESOURCE_CREATED = "resource.created"
RESOURCE_UPDATED = "resource.updated"
RESOURCE_ARCHIVED = "resource.archived"
RESOURCE_FACT_TYPES = frozenset({RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_ARCHIVED})
CANON_BUSINESS_RESOURCE_PROJECTOR = True
CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER = True


class BusinessResourceHistoryInvariantViolation(RuntimeError):
    pass


class BusinessResourceProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, resource_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in RESOURCE_FACT_TYPES or (resource_id is not None and entity_id != str(resource_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    @staticmethod
    def _assert_schema(payload: dict[str, object]) -> None:
        value = payload.get("schema_version")
        if isinstance(value, bool) or value != BUSINESS_RESOURCE_SCHEMA_VERSION:
            raise BusinessResourceHistoryInvariantViolation("business resource history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, resource_id: str) -> BusinessResource:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)
        if not facts:
            raise BusinessResourceNotFound(f"business resource not found: {resource_id}")
        created_rows = [row for row in facts if row["fact_type"] == RESOURCE_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise BusinessResourceHistoryInvariantViolation(
                "business resource history must begin with exactly one create fact"
            )
        created = created_rows[0]
        payload = dict(created["payload"])
        self._assert_schema(payload)
        resource = BusinessResource(
            resource_id=str(resource_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            resource_kind=payload.get("resource_kind"),
            state_key=payload.get("state_key"),
            asset_id=payload.get("asset_id"),
            schema_version=payload.get("schema_version"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if resource.lifecycle_status is ResourceLifecycleStatus.ARCHIVED:
                raise BusinessResourceHistoryInvariantViolation("business resource history continues after archive")
            when = int(row["event_time_ms"])
            update = dict(row["payload"])
            self._assert_schema(update)
            if row["fact_type"] == RESOURCE_UPDATED:
                next_kind = update.get("resource_kind", resource.resource_kind)
                next_asset = update.get("asset_id", resource.asset_id)
                if next_kind != resource.resource_kind:
                    raise BusinessResourceHistoryInvariantViolation("business resource kind cannot be rewritten")
                if next_asset != resource.asset_id:
                    raise BusinessResourceHistoryInvariantViolation("business resource asset relation cannot be rewritten")
                resource = replace(
                    resource,
                    state_key=update.get("state_key", resource.state_key),
                    updated_at_ms=max(resource.updated_at_ms, when),
                )
            elif row["fact_type"] == RESOURCE_ARCHIVED:
                resource = replace(
                    resource,
                    lifecycle_status=ResourceLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(resource.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return resource

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessResource, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, resource_id=value) for value in ids)


class BusinessResourceRegistry:
    """Single business Resource lifecycle writer over the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = BusinessResourceProjector(event_store)
        self._assets = AssetProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="business_resource_fact",
            source="business_resource_registry",
            id_prefix="business-resource",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(resource: BusinessResource) -> dict[str, object]:
        return {
            "schema_version": resource.schema_version,
            "resource_kind": resource.resource_kind,
            "state_key": resource.state_key,
            "asset_id": resource.asset_id,
        }

    @staticmethod
    def _state_token(resource: BusinessResource) -> str:
        return "|".join((
            resource.lifecycle_status.value,
            str(resource.updated_at_ms),
            str(resource.schema_version),
            resource.resource_kind,
            resource.state_key or "",
            resource.asset_id or "",
        ))

    def _assert_asset_relation(self, *, tenant_id: str, business_id: str, asset_id: str | None) -> None:
        if asset_id is None:
            return
        try:
            asset = self._assets.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)
        except LookupError as exc:
            raise ValueError("business resource asset relation must reference a canonical asset") from exc
        if asset.lifecycle_status is not AssetLifecycleStatus.ACTIVE:
            raise ValueError("business resource asset relation must reference an active asset")

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        resource_id: str,
        idempotency_key: str,
        resource_kind: str,
        state_key: str | None = None,
        asset_id: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> BusinessResource:
        when = self._time(occurred_at_ms)
        candidate = BusinessResource(
            resource_id=resource_id,
            tenant_id=tenant_id,
            business_id=business_id,
            resource_kind=resource_kind,
            state_key=state_key,
            asset_id=asset_id,
            created_at_ms=when,
            updated_at_ms=when,
        )
        self._assert_asset_relation(tenant_id=candidate.tenant_id, business_id=candidate.business_id, asset_id=candidate.asset_id)
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("business resource already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=resource_id,
                operation="create", idempotency_key=idempotency_key, fact_type=RESOURCE_CREATED, payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=resource_id,
            operation="create", idempotency_key=idempotency_key, fact_type=RESOURCE_CREATED,
            payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        resource_id: str,
        idempotency_key: str,
        resource_kind: str | None = None,
        state_key: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> BusinessResource:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)
        if current.lifecycle_status is ResourceLifecycleStatus.ARCHIVED:
            raise ValueError("archived business resource cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = BusinessResource(
            resource_id=current.resource_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            resource_kind=current.resource_kind if resource_kind is None else resource_kind,
            state_key=current.state_key if state_key is None else state_key,
            asset_id=current.asset_id,
            created_at_ms=current.created_at_ms,
            updated_at_ms=when,
        )
        if candidate.resource_kind != current.resource_kind:
            raise ValueError("business resource kind cannot be rewritten")
        payload = self._payload(candidate)
        if payload == self._payload(current):
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=resource_id,
            expected_state_token=self._state_token(current), operation="update",
            idempotency_key=idempotency_key, fact_type=RESOURCE_UPDATED, payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        resource_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> BusinessResource:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)
        if current.lifecycle_status is ResourceLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        payload: dict[str, object] = {"schema_version": BUSINESS_RESOURCE_SCHEMA_VERSION}
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=resource_id,
            expected_state_token=self._state_token(current), operation="archive",
            idempotency_key=idempotency_key, fact_type=RESOURCE_ARCHIVED, payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)

    def get(self, *, tenant_id: str, business_id: str, resource_id: str) -> BusinessResource:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, resource_id=resource_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessResource, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER",
    "CANON_BUSINESS_RESOURCE_PROJECTOR",
    "RESOURCE_FACT_TYPES",
    "BusinessResourceHistoryInvariantViolation",
    "BusinessResourceProjector",
    "BusinessResourceRegistry",
]
