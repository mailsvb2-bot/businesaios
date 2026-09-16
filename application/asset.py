from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.asset import ASSET_SCHEMA_VERSION, Asset, AssetLifecycleStatus, AssetNotFound
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

ASSET_CREATED = "asset.created"
ASSET_UPDATED = "asset.updated"
ASSET_ARCHIVED = "asset.archived"
ASSET_FACT_TYPES = frozenset({ASSET_CREATED, ASSET_UPDATED, ASSET_ARCHIVED})
CANON_ASSET_PROJECTOR = True
CANON_ASSET_LIFECYCLE_OWNER = True


class AssetHistoryInvariantViolation(RuntimeError):
    pass


class AssetProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, asset_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in ASSET_FACT_TYPES or (asset_id is not None and entity_id != str(asset_id)):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                    "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    @staticmethod
    def _assert_schema(payload: dict[str, object]) -> None:
        value = payload.get("schema_version")
        if isinstance(value, bool) or value != ASSET_SCHEMA_VERSION:
            raise AssetHistoryInvariantViolation("asset history has unsupported schema_version")

    def get(self, *, tenant_id: str, business_id: str, asset_id: str) -> Asset:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)
        if not facts:
            raise AssetNotFound(f"asset not found: {asset_id}")
        created_rows = [row for row in facts if row["fact_type"] == ASSET_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise AssetHistoryInvariantViolation("asset history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        self._assert_schema(payload)
        asset = Asset(
            asset_id=str(asset_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            asset_kind=payload.get("asset_kind"),
            state_key=payload.get("state_key"),
            book_value_minor=payload.get("book_value_minor"),
            currency=payload.get("currency"),
            schema_version=payload.get("schema_version"),
            created_at_ms=int(created["event_time_ms"]),
            updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if asset.lifecycle_status is AssetLifecycleStatus.ARCHIVED:
                raise AssetHistoryInvariantViolation("asset history continues after archive")
            when = int(row["event_time_ms"])
            if row["fact_type"] == ASSET_UPDATED:
                update = dict(row["payload"])
                self._assert_schema(update)
                next_kind = update.get("asset_kind", asset.asset_kind)
                next_currency = update.get("currency", asset.currency)
                if next_kind != asset.asset_kind:
                    raise AssetHistoryInvariantViolation("asset kind cannot be rewritten")
                if asset.currency is not None and next_currency != asset.currency:
                    raise AssetHistoryInvariantViolation("asset currency cannot be rewritten")
                asset = replace(
                    asset,
                    state_key=update.get("state_key", asset.state_key),
                    book_value_minor=update.get("book_value_minor", asset.book_value_minor),
                    currency=next_currency,
                    updated_at_ms=max(asset.updated_at_ms, when),
                )
            elif row["fact_type"] == ASSET_ARCHIVED:
                update = dict(row["payload"])
                self._assert_schema(update)
                asset = replace(
                    asset,
                    lifecycle_status=AssetLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(asset.updated_at_ms, when),
                    archived_at_ms=when,
                )
        return asset

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Asset, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, asset_id=value) for value in ids)


class AssetRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = AssetProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="asset_fact",
            source="asset_registry",
            id_prefix="asset",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(asset: Asset) -> dict[str, object]:
        return {
            "schema_version": asset.schema_version,
            "asset_kind": asset.asset_kind,
            "state_key": asset.state_key,
            "book_value_minor": asset.book_value_minor,
            "currency": asset.currency,
        }

    @staticmethod
    def _state_token(asset: Asset) -> str:
        return "|".join(
            (
                asset.lifecycle_status.value,
                str(asset.updated_at_ms),
                str(asset.schema_version),
                asset.asset_kind,
                asset.state_key or "",
                "" if asset.book_value_minor is None else str(asset.book_value_minor),
                asset.currency or "",
            )
        )

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        asset_id: str,
        idempotency_key: str,
        asset_kind: str,
        state_key: str | None = None,
        book_value_minor: int | None = None,
        currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Asset:
        when = self._time(occurred_at_ms)
        candidate = Asset(
            asset_id=asset_id,
            tenant_id=tenant_id,
            business_id=business_id,
            asset_kind=asset_kind,
            state_key=state_key,
            book_value_minor=book_value_minor,
            currency=currency,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("asset already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=asset_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=ASSET_CREATED,
                payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=asset_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=ASSET_CREATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        asset_id: str,
        idempotency_key: str,
        asset_kind: str | None = None,
        state_key: str | None = None,
        book_value_minor: int | None = None,
        currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Asset:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)
        if current.lifecycle_status is AssetLifecycleStatus.ARCHIVED:
            raise ValueError("archived asset cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Asset(
            asset_id=current.asset_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            asset_kind=current.asset_kind if asset_kind is None else asset_kind,
            state_key=current.state_key if state_key is None else state_key,
            book_value_minor=current.book_value_minor if book_value_minor is None else book_value_minor,
            currency=current.currency if currency is None else currency,
            created_at_ms=current.created_at_ms,
            updated_at_ms=when,
        )
        if candidate.asset_kind != current.asset_kind:
            raise ValueError("asset kind cannot be rewritten")
        if current.currency is not None and candidate.currency != current.currency:
            raise ValueError("asset currency cannot be rewritten")
        payload = self._payload(candidate)
        if payload == self._payload(current):
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=asset_id,
            expected_state_token=self._state_token(current),
            operation="update",
            idempotency_key=idempotency_key,
            fact_type=ASSET_UPDATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        asset_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Asset:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)
        if current.lifecycle_status is AssetLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        payload: dict[str, object] = {"schema_version": ASSET_SCHEMA_VERSION}
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=asset_id,
            expected_state_token=self._state_token(current),
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=ASSET_ARCHIVED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)

    def get(self, *, tenant_id: str, business_id: str, asset_id: str) -> Asset:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, asset_id=asset_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Asset, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "ASSET_FACT_TYPES",
    "CANON_ASSET_LIFECYCLE_OWNER",
    "CANON_ASSET_PROJECTOR",
    "AssetHistoryInvariantViolation",
    "AssetProjector",
    "AssetRegistry",
]
