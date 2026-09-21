from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

from contracts.event_store import canonical_business_event_contract
from contracts.order import ORDER_SCHEMA_VERSION, Order, OrderLifecycleStatus, OrderNotFound
from core.events.event_types import (
    ORDER_ARCHIVED,
    ORDER_CANCELLED,
    ORDER_CREATED,
    ORDER_FULFILLED,
    ORDER_UPDATED,
)
from core.finance.money import legacy_float, money_decimal
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage
from registry.base_registry import BaseRegistry, RegistryBackend

CANON_ORDER_LIFECYCLE_OWNER = True
CANON_ORDER_EVENT_SPINE_PROJECTION = True
CANON_CLIENT_OUTCOME_ORDER_STORE = True
_ORDER_EVENT_NAMESPACE = UUID("1bedb24f-71ad-46f4-94fc-748543bcd789")
CLIENT_OUTCOME_ORDER_KIND = "client_outcome"
LEGACY_CLIENT_OUTCOME_ORDER_NAMESPACE = "client_outcome_order"

_ALLOWED_TRANSITIONS = {
    OrderLifecycleStatus.ACTIVE: frozenset({
        OrderLifecycleStatus.FULFILLED,
        OrderLifecycleStatus.CANCELLED,
        OrderLifecycleStatus.ARCHIVED,
    }),
    OrderLifecycleStatus.FULFILLED: frozenset(),
    OrderLifecycleStatus.CANCELLED: frozenset(),
    OrderLifecycleStatus.ARCHIVED: frozenset(),
}


def _as_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"corrupt canonical order {field_name}")
    return dict(value)


def _epoch_ms(value: datetime) -> int:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return max(0, int(instant.timestamp() * 1000))


def _legacy_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _OrderEventSpineProjection:
    _TERMINAL_TYPES = {
        OrderLifecycleStatus.FULFILLED: ORDER_FULFILLED,
        OrderLifecycleStatus.CANCELLED: ORDER_CANCELLED,
        OrderLifecycleStatus.ARCHIVED: ORDER_ARCHIVED,
    }

    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    @staticmethod
    def _specialization_projection(specialization: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(specialization or {})
        package = _as_mapping(row.get("package", {}), field_name="order specialization package")
        return {
            "kind": str(row.get("kind") or "").strip() or None,
            "package_id": str(package.get("package_id") or "").strip() or None,
            "requested_clients": package.get("requested_clients"),
            "currency": str(package.get("currency") or "").strip() or None,
            "attribution_window_days": package.get("attribution_window_days"),
            "new_client_window_days": package.get("new_client_window_days"),
            "allow_returning_clients": package.get("allow_returning_clients"),
            "require_payment_proof": package.get("require_payment_proof"),
            "require_crm_proof": package.get("require_crm_proof"),
            "trust_tier": str(package.get("trust_tier") or "").strip() or None,
        }

    @classmethod
    def _event_id(
        cls,
        *,
        order: Order,
        event_type: str,
        occurred_at_ms: int,
        specialization: Mapping[str, Any],
    ) -> str:
        specialization_key = ""
        if event_type == ORDER_UPDATED:
            specialization_key = _legacy_fingerprint(cls._specialization_projection(specialization))
        semantic = ":".join(
            (
                order.tenant_id,
                order.business_id,
                order.order_id,
                event_type,
                str(int(occurred_at_ms)),
                specialization_key,
            )
        )
        return str(uuid5(_ORDER_EVENT_NAMESPACE, semantic))

    def _matches(
        self,
        *,
        order: Order,
        event_type: str,
        event_id: str,
    ) -> list[dict[str, Any]]:
        return [
            dict(raw)
            for raw in self._events.iter_events(
                tenant_id=order.tenant_id,
                start_ms=0,
                event_type=event_type,
            )
            if str(raw.get("event_id") or "") == event_id
        ]

    def _append(
        self,
        *,
        order: Order,
        specialization: Mapping[str, Any],
        event_type: str,
        occurred_at_ms: int,
        lifecycle_status: OrderLifecycleStatus,
        updated_at_ms: int,
        terminal_at_ms: int | None,
    ) -> str:
        event_id = self._event_id(
            order=order,
            event_type=event_type,
            occurred_at_ms=occurred_at_ms,
            specialization=specialization,
        )
        payload: dict[str, Any] = {
            "schema_version": 1,
            "business_id": order.business_id,
            "occurred_at_ms": int(occurred_at_ms),
            "recorded_at_ms": int(occurred_at_ms),
            "order_id": order.order_id,
            "order_schema_version": order.schema_version,
            "order_kind": order.order_kind,
            "state_key": order.state_key,
            "lifecycle_status": lifecycle_status.value,
            "created_at_ms": order.created_at_ms,
            "updated_at_ms": int(updated_at_ms),
            "terminal_at_ms": terminal_at_ms,
        }
        if event_type == ORDER_UPDATED:
            payload["specialization"] = self._specialization_projection(specialization)
        event = {
            "event_id": event_id,
            "tenant_id": order.tenant_id,
            "source": "lead_outcomes.order_store",
            "event_type": event_type,
            "timestamp_ms": int(occurred_at_ms),
            "decision_id": None,
            "correlation_id": None,
            "payload": payload,
        }
        matches = self._matches(order=order, event_type=event_type, event_id=event_id)
        if len(matches) > 1:
            raise RuntimeError("ORDER_EVENT_SPINE_DUPLICATE")
        if matches:
            if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
                raise RuntimeError("ORDER_EVENT_SPINE_CONFLICT")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            matches = self._matches(order=order, event_type=event_type, event_id=event_id)
            if (
                len(matches) != 1
                or canonical_business_event_contract(matches[0])
                != canonical_business_event_contract(event)
            ):
                raise
            return event_id
        matches = self._matches(order=order, event_type=event_type, event_id=event_id)
        if len(matches) != 1:
            raise RuntimeError("ORDER_EVENT_SPINE_APPEND_NOT_DURABLE")
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise RuntimeError("ORDER_EVENT_SPINE_CONFLICT")
        return event_id

    def project_current(self, *, order: Order, specialization: Mapping[str, Any]) -> None:
        self._append(
            order=order,
            specialization={},
            event_type=ORDER_CREATED,
            occurred_at_ms=order.created_at_ms,
            lifecycle_status=OrderLifecycleStatus.ACTIVE,
            updated_at_ms=order.created_at_ms,
            terminal_at_ms=None,
        )
        if order.lifecycle_status is OrderLifecycleStatus.ACTIVE:
            if order.updated_at_ms > order.created_at_ms:
                self._append(
                    order=order,
                    specialization=specialization,
                    event_type=ORDER_UPDATED,
                    occurred_at_ms=order.updated_at_ms,
                    lifecycle_status=OrderLifecycleStatus.ACTIVE,
                    updated_at_ms=order.updated_at_ms,
                    terminal_at_ms=None,
                )
            return
        event_type = self._TERMINAL_TYPES[order.lifecycle_status]
        self._append(
            order=order,
            specialization={},
            event_type=event_type,
            occurred_at_ms=order.updated_at_ms,
            lifecycle_status=order.lifecycle_status,
            updated_at_ms=order.updated_at_ms,
            terminal_at_ms=order.terminal_at_ms,
        )


class OrderStore(BaseRegistry):
    """Single canonical Order owner with client-outcome compatibility projection."""

    def __init__(
        self,
        *,
        backend: RegistryBackend | None = None,
        legacy_backend: RegistryBackend | None = None,
        event_store: Any | None = None,
        require_event_spine: bool = False,
    ) -> None:
        super().__init__(kind="order", backend=backend)
        if require_event_spine and event_store is None:
            raise RuntimeError("ORDER_EVENT_STORE_REQUIRED")
        self._event_spine = None if event_store is None else _OrderEventSpineProjection(event_store)
        self._legacy_backend = legacy_backend
        if legacy_backend is not None:
            self._migrate_legacy_orders()

    def repair_event_spine(self, order_id: str) -> Order:
        payload = self.maybe_get(str(order_id))
        if payload is None:
            raise OrderNotFound(f"order not found: {order_id}")
        order, specialization, _ = self._decode_envelope(payload)
        if self._event_spine is not None:
            self._event_spine.project_current(order=order, specialization=specialization)
        return order

    def _project(self, *, order: Order, specialization: Mapping[str, Any]) -> None:
        if self._event_spine is not None:
            self._event_spine.project_current(order=order, specialization=specialization)

    @staticmethod
    def _serialize_order(order: Order) -> dict[str, Any]:
        return {
            "order_id": order.order_id,
            "tenant_id": order.tenant_id,
            "business_id": order.business_id,
            "order_kind": order.order_kind,
            "state_key": order.state_key,
            "schema_version": order.schema_version,
            "lifecycle_status": order.lifecycle_status.value,
            "created_at_ms": order.created_at_ms,
            "updated_at_ms": order.updated_at_ms,
            "terminal_at_ms": order.terminal_at_ms,
        }

    @staticmethod
    def _deserialize_order(payload: Mapping[str, Any]) -> Order:
        row = dict(payload)
        try:
            return Order(
                order_id=row["order_id"],
                tenant_id=row["tenant_id"],
                business_id=row["business_id"],
                order_kind=row["order_kind"],
                state_key=row.get("state_key"),
                schema_version=row.get("schema_version", 0),
                lifecycle_status=row.get("lifecycle_status", ""),
                created_at_ms=row.get("created_at_ms", -1),
                updated_at_ms=row.get("updated_at_ms", -1),
                terminal_at_ms=row.get("terminal_at_ms"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("corrupt canonical order payload") from exc

    @classmethod
    def _decode_envelope(
        cls,
        payload: object,
    ) -> tuple[Order, dict[str, Any], dict[str, Any]]:
        envelope = _as_mapping(payload, field_name="envelope")
        if envelope.get("schema_version") != ORDER_SCHEMA_VERSION:
            raise RuntimeError("unsupported canonical order envelope schema")
        order = cls._deserialize_order(_as_mapping(envelope.get("order"), field_name="order"))
        specialization = _as_mapping(envelope.get("specialization", {}), field_name="specialization")
        migration = _as_mapping(envelope.get("migration", {}), field_name="migration")
        return order, specialization, migration

    @classmethod
    def _envelope(
        cls,
        *,
        order: Order,
        specialization: Mapping[str, Any] | None = None,
        migration: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": ORDER_SCHEMA_VERSION,
            "order": cls._serialize_order(order),
            "specialization": dict(specialization or {}),
            "migration": dict(migration or {}),
        }

    def create_order(
        self,
        order: Order,
        *,
        specialization: Mapping[str, Any] | None = None,
    ) -> Order:
        if order.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            raise ValueError("new order must be active")
        candidate = self._envelope(order=order, specialization=specialization)
        existing = self.maybe_get(order.order_id)
        if existing is not None:
            current, current_specialization, _ = self._decode_envelope(existing)
            self._project(order=current, specialization=current_specialization)
            if current != order or current_specialization != dict(specialization or {}):
                raise ValueError("order_id already exists with different identity or state")
            return current
        self.register_unique(order.order_id, candidate, error_prefix="order")
        self._project(order=order, specialization=dict(specialization or {}))
        return order

    def get_canonical_order(
        self,
        order_id: str,
        *,
        tenant_id: str | None = None,
        business_id: str | None = None,
    ) -> Order:
        payload = self.maybe_get(str(order_id))
        if payload is None:
            raise OrderNotFound(f"order not found: {order_id}")
        order, _, _ = self._decode_envelope(payload)
        if tenant_id is not None and order.tenant_id != str(tenant_id).strip():
            raise OrderNotFound(f"order not found: {order_id}")
        if business_id is not None and order.business_id != str(business_id).strip():
            raise OrderNotFound(f"order not found: {order_id}")
        return order

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Order, ...]:
        tenant = str(tenant_id).strip()
        business = str(business_id).strip()
        rows: list[Order] = []
        for _, payload in self.items():
            order, _, _ = self._decode_envelope(payload)
            if order.tenant_id == tenant and order.business_id == business:
                rows.append(order)
        return tuple(sorted(rows, key=lambda item: (item.created_at_ms, item.order_id)))

    def transition_order(
        self,
        *,
        order_id: str,
        tenant_id: str,
        business_id: str,
        lifecycle_status: OrderLifecycleStatus | str,
        occurred_at_ms: int,
    ) -> Order:
        payload = self.maybe_get(str(order_id))
        if payload is None:
            raise OrderNotFound(f"order not found: {order_id}")
        current, specialization, migration = self._decode_envelope(payload)
        if current.tenant_id != str(tenant_id).strip() or current.business_id != str(business_id).strip():
            raise OrderNotFound(f"order not found: {order_id}")
        self._project(order=current, specialization=specialization)
        target = OrderLifecycleStatus(lifecycle_status)
        if target is current.lifecycle_status:
            return current
        if target not in _ALLOWED_TRANSITIONS[current.lifecycle_status]:
            raise ValueError(
                f"invalid order transition: {current.lifecycle_status.value}->{target.value}"
            )
        when = int(occurred_at_ms)
        if when < current.updated_at_ms:
            raise ValueError("order transition timestamp cannot move backwards")
        updated = replace(
            current,
            lifecycle_status=target,
            updated_at_ms=when,
            terminal_at_ms=when,
        )
        self.register(
            current.order_id,
            self._envelope(
                order=updated,
                specialization=specialization,
                migration=migration,
            ),
        )
        self._project(order=updated, specialization=specialization)
        return updated

    @staticmethod
    def _package_payload(package: ClientOutcomePackage) -> dict[str, Any]:
        normalized = package.normalized_copy()
        return {
            "package_id": normalized.package_id,
            "label": normalized.label,
            "requested_clients": normalized.requested_clients,
            "price_per_verified_client": normalized.price_per_verified_client,
            "currency": normalized.currency,
            "attribution_window_days": normalized.attribution_window_days,
            "new_client_window_days": normalized.new_client_window_days,
            "allow_returning_clients": normalized.allow_returning_clients,
            "require_payment_proof": normalized.require_payment_proof,
            "require_crm_proof": normalized.require_crm_proof,
            "trust_tier": normalized.trust_tier,
        }

    @classmethod
    def _specialization_payload(cls, order: ClientOutcomeOrder) -> dict[str, Any]:
        return {
            "kind": CLIENT_OUTCOME_ORDER_KIND,
            "package": cls._package_payload(order.package),
            "created_at": order.created_at.isoformat(),
            "metadata": dict(order.metadata),
        }

    @staticmethod
    def _updated_at_ms(order: ClientOutcomeOrder) -> int:
        created = _epoch_ms(order.created_at)
        metadata = dict(order.metadata)
        last_amendment = metadata.get("last_amendment")
        raw = ""
        if isinstance(last_amendment, Mapping):
            raw = str(last_amendment.get("amended_at") or "").strip()
        if not raw:
            amendments = metadata.get("amendments")
            if isinstance(amendments, list) and amendments and isinstance(amendments[-1], Mapping):
                raw = str(amendments[-1].get("amended_at") or "").strip()
        if not raw:
            return created
        try:
            amended = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("invalid client outcome amendment timestamp") from exc
        return max(created, _epoch_ms(amended))

    @classmethod
    def _canonical_from_client_order(cls, order: ClientOutcomeOrder) -> Order:
        created = _epoch_ms(order.created_at)
        return Order(
            order_id=order.order_id,
            tenant_id=order.tenant_id,
            business_id=order.business_id,
            order_kind=CLIENT_OUTCOME_ORDER_KIND,
            created_at_ms=created,
            updated_at_ms=cls._updated_at_ms(order),
        )

    @staticmethod
    def _package_from_payload(payload: Mapping[str, Any]) -> ClientOutcomePackage:
        row = dict(payload)
        try:
            return ClientOutcomePackage(
                package_id=str(row["package_id"]),
                label=str(row["label"]),
                requested_clients=int(row["requested_clients"]),
                price_per_verified_client=legacy_float(
                    money_decimal(row["price_per_verified_client"], name="price_per_verified_client"),
                    name="price_per_verified_client",
                ),
                currency=str(row["currency"]),
                attribution_window_days=int(row["attribution_window_days"]),
                new_client_window_days=int(row["new_client_window_days"]),
                allow_returning_clients=bool(row["allow_returning_clients"]),
                require_payment_proof=bool(row["require_payment_proof"]),
                require_crm_proof=bool(row["require_crm_proof"]),
                trust_tier=str(row["trust_tier"]),
            ).normalized_copy()
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("corrupt client outcome order package") from exc

    @classmethod
    def _client_order_from_specialization(
        cls,
        *,
        canonical_order: Order,
        specialization: Mapping[str, Any],
    ) -> ClientOutcomeOrder:
        row = dict(specialization)
        if row.get("kind") != CLIENT_OUTCOME_ORDER_KIND:
            raise RuntimeError("canonical order specialization kind mismatch")
        package = cls._package_from_payload(
            _as_mapping(row.get("package"), field_name="client outcome package")
        )
        try:
            created_at = datetime.fromisoformat(str(row["created_at"]))
        except (KeyError, ValueError) as exc:
            raise RuntimeError("corrupt client outcome order created_at") from exc
        metadata = _as_mapping(
            row.get("metadata", {}),
            field_name="client outcome metadata",
        )
        if _epoch_ms(created_at) != canonical_order.created_at_ms:
            raise RuntimeError("client outcome created_at disagrees with canonical order")
        return ClientOutcomeOrder(
            order_id=canonical_order.order_id,
            tenant_id=canonical_order.tenant_id,
            business_id=canonical_order.business_id,
            package=package,
            created_at=created_at,
            metadata=metadata,
        )

    @classmethod
    def _legacy_order_from_payload(cls, payload: Mapping[str, Any]) -> ClientOutcomeOrder:
        row = dict(payload)
        package = cls._package_from_payload(
            _as_mapping(row.get("package"), field_name="legacy client outcome package")
        )
        try:
            created_at = datetime.fromisoformat(str(row["created_at"]))
        except (KeyError, ValueError) as exc:
            raise RuntimeError("corrupt legacy client outcome order created_at") from exc
        metadata = _as_mapping(
            row.get("metadata", {}),
            field_name="legacy client outcome metadata",
        )
        try:
            return ClientOutcomeOrder(
                order_id=str(row["order_id"]),
                tenant_id=str(row["tenant_id"]),
                business_id=str(row["business_id"]),
                package=package,
                created_at=created_at,
                metadata=metadata,
            )
        except KeyError as exc:
            raise RuntimeError("corrupt legacy client outcome order identity") from exc

    @staticmethod
    def _migration_payload(*, fingerprint: str) -> dict[str, Any]:
        return {
            "source_namespace": LEGACY_CLIENT_OUTCOME_ORDER_NAMESPACE,
            "legacy_fingerprint": str(fingerprint),
        }

    def _migrate_legacy_orders(self) -> None:
        assert self._legacy_backend is not None
        for item_key, raw_payload in self._legacy_backend.items():
            payload = _as_mapping(raw_payload, field_name="legacy order payload")
            legacy_order = self._legacy_order_from_payload(payload)
            if str(item_key) != legacy_order.order_id:
                raise RuntimeError("legacy client outcome order key mismatch")
            fingerprint = _legacy_fingerprint(payload)
            migration = self._migration_payload(fingerprint=fingerprint)
            existing = self.maybe_get(legacy_order.order_id)
            if existing is None:
                canonical = self._canonical_from_client_order(legacy_order)
                self.register_unique(
                    legacy_order.order_id,
                    self._envelope(
                        order=canonical,
                        specialization=self._specialization_payload(legacy_order),
                        migration=migration,
                    ),
                    error_prefix="order",
                )
                self._project(order=canonical, specialization=self._specialization_payload(legacy_order))
                continue

            canonical, specialization, current_migration = self._decode_envelope(existing)
            if canonical.order_kind != CLIENT_OUTCOME_ORDER_KIND:
                raise RuntimeError("legacy order conflicts with non-client-outcome canonical order")
            recorded = str(current_migration.get("legacy_fingerprint") or "").strip()
            source = str(current_migration.get("source_namespace") or "").strip()
            if recorded:
                if source != LEGACY_CLIENT_OUTCOME_ORDER_NAMESPACE or recorded != fingerprint:
                    raise RuntimeError("legacy client outcome order diverged after canonical migration")
                self._project(order=canonical, specialization=specialization)
                continue
            projected = self._client_order_from_specialization(
                canonical_order=canonical,
                specialization=specialization,
            )
            if projected != legacy_order:
                raise RuntimeError("legacy client outcome order conflicts with canonical order")
            self.register(
                canonical.order_id,
                self._envelope(
                    order=canonical,
                    specialization=specialization,
                    migration=migration,
                ),
            )
            self._project(order=canonical, specialization=specialization)

    def save(self, order: ClientOutcomeOrder) -> None:
        canonical = self._canonical_from_client_order(order)
        specialization = self._specialization_payload(order)
        existing = self.maybe_get(order.order_id)
        if existing is None:
            self.create_order(canonical, specialization=specialization)
            return

        current, current_specialization, migration = self._decode_envelope(existing)
        self._project(order=current, specialization=current_specialization)
        if current.order_kind != CLIENT_OUTCOME_ORDER_KIND:
            raise ValueError("order_id is owned by a different order kind")
        immutable_identity = (
            current.order_id,
            current.tenant_id,
            current.business_id,
            current.order_kind,
            current.created_at_ms,
        )
        candidate_identity = (
            canonical.order_id,
            canonical.tenant_id,
            canonical.business_id,
            canonical.order_kind,
            canonical.created_at_ms,
        )
        if candidate_identity != immutable_identity:
            raise ValueError("client outcome order identity is immutable")
        if current.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            raise ValueError("terminal client outcome order cannot be modified")
        if canonical.updated_at_ms < current.updated_at_ms:
            if specialization == current_specialization:
                return
            raise ValueError("client outcome order update timestamp cannot move backwards")
        updated = replace(
            current,
            updated_at_ms=max(current.updated_at_ms, canonical.updated_at_ms),
        )
        if updated == current and specialization == current_specialization:
            return
        self.register(
            current.order_id,
            self._envelope(
                order=updated,
                specialization=specialization,
                migration=migration,
            ),
        )
        self._project(order=updated, specialization=specialization)

    def get_order(self, order_id: str) -> ClientOutcomeOrder | None:
        payload = self.maybe_get(str(order_id))
        if payload is None:
            return None
        canonical, specialization, _ = self._decode_envelope(payload)
        if canonical.order_kind != CLIENT_OUTCOME_ORDER_KIND:
            return None
        return self._client_order_from_specialization(
            canonical_order=canonical,
            specialization=specialization,
        )

    def amend_order(
        self,
        *,
        now: datetime,
        order_id: str,
        package: ClientOutcomePackage,
        metadata: dict[str, Any] | None = None,
    ) -> ClientOutcomeOrder | None:
        current = self.get_order(order_id)
        if current is None:
            return None
        canonical = self.get_canonical_order(
            order_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
        )
        if canonical.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            raise ValueError("terminal client outcome order cannot be amended")
        normalized_package = package.normalized_copy()
        amendment_meta = dict(metadata or {})
        amendments = list(current.metadata.get("amendments") or [])
        next_count = int(current.metadata.get("amendment_count") or 0) + 1
        amendments.append({
            "amendment_index": next_count,
            "amended_at": now.isoformat(),
            "from_package_id": current.package.package_id,
            "to_package_id": normalized_package.package_id,
            "from_requested_clients": current.package.requested_clients,
            "to_requested_clients": normalized_package.requested_clients,
            "from_price_per_verified_client": current.package.price_per_verified_client,
            "to_price_per_verified_client": normalized_package.price_per_verified_client,
            "currency": normalized_package.currency,
            "metadata": amendment_meta,
        })
        next_metadata = dict(current.metadata)
        amendment_fingerprints = list(current.metadata.get("amendment_fingerprints") or ())
        amendment_fingerprint_value = amendment_meta.get("amendment_fingerprint")
        if (
            amendment_fingerprint_value not in (None, "")
            and str(amendment_fingerprint_value) not in amendment_fingerprints
        ):
            amendment_fingerprints.append(str(amendment_fingerprint_value))
        next_metadata["amendment_count"] = next_count
        next_metadata["amendments"] = amendments
        next_metadata["amendment_fingerprints"] = amendment_fingerprints
        next_metadata["last_amendment"] = {
            **amendment_meta,
            "amended_at": now.isoformat(),
        }
        amended = replace(
            current,
            package=normalized_package,
            metadata=next_metadata,
        )
        self.save(amended)
        return amended


ClientOutcomeOrderStore = OrderStore


@dataclass(frozen=True, slots=True)
class ClientOutcomeOrderPersistenceService:
    store: OrderStore

    def repair_event_spine(self, order_id: str) -> Order:
        return self.store.repair_event_spine(order_id)

    def persist(self, order: ClientOutcomeOrder) -> ClientOutcomeOrder:
        self.store.save(order)
        return order

    def get_order(self, order_id: str) -> ClientOutcomeOrder | None:
        return self.store.get_order(order_id)

    def amend_order(
        self,
        *,
        now: datetime,
        order_id: str,
        package: ClientOutcomePackage,
        metadata: dict[str, Any] | None = None,
    ) -> ClientOutcomeOrder | None:
        return self.store.amend_order(
            now=now,
            order_id=order_id,
            package=package,
            metadata=metadata,
        )


__all__ = [
    "CANON_CLIENT_OUTCOME_ORDER_STORE",
    "CANON_ORDER_EVENT_SPINE_PROJECTION",
    "CANON_ORDER_LIFECYCLE_OWNER",
    "CLIENT_OUTCOME_ORDER_KIND",
    "ClientOutcomeOrderPersistenceService",
    "ClientOutcomeOrderStore",
    "OrderStore",
]
