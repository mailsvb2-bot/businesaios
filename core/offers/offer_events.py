from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid5

from contracts.event_store import append_event_strict, canonical_business_event_contract
from core.events.event_types import OFFER_CREATED, OFFER_UPDATED

# Canonical offer funnel events (Ring).
OFFER_SHOWN_V1 = "offer_shown@v1"
OFFER_ACCEPTED_V1 = "offer_accepted@v1"
OFFER_DECLINED_V1 = "offer_declined@v1"
OFFER_EXPIRED_V1 = "offer_expired@v1"

CANON_OFFER_EVENT_SPINE_PROJECTION = True
_OFFER_EVENT_NAMESPACE = UUID("0d1d957c-d0af-4dc9-9704-391aabcf6294")


def _required(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    return text


def _event_id(
    *,
    tenant_id: str,
    business_id: str,
    product_id: str,
    environment: str,
    offer_id: str,
    catalog_revision: str,
    mutation_kind: str,
    event_type: str,
) -> str:
    semantic = ":".join(
        (
            tenant_id,
            business_id,
            product_id,
            environment,
            offer_id,
            catalog_revision,
            mutation_kind,
            event_type,
        )
    )
    return str(uuid5(_OFFER_EVENT_NAMESPACE, semantic))


def _matches(event_store: Any, *, tenant_id: str, event_type: str, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(raw)
        for raw in event_store.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=event_type,
        )
        if str(raw.get("event_id") or "") == event_id
    ]


def _validate_existing(
    raw: dict[str, Any],
    *,
    business_id: str,
    product_id: str,
    environment: str,
    offer_id: str,
    catalog_revision: str,
    mutation_kind: str,
) -> None:
    canonical = canonical_business_event_contract(raw)
    payload = dict(canonical.get("payload") or {})
    if (
        canonical.get("business_id") != business_id
        or str(payload.get("product_id") or "") != product_id
        or str(payload.get("environment") or "") != environment
        or str(payload.get("offer_id") or "") != offer_id
        or str(payload.get("catalog_revision") or "") != catalog_revision
        or str(payload.get("mutation_kind") or "") != mutation_kind
    ):
        raise RuntimeError("OFFER_EVENT_SPINE_CONFLICT")


def find_offer_catalog_event(
    event_store: Any,
    *,
    tenant_id: str,
    business_id: str,
    product_id: str,
    environment: str,
    offer_id: str,
    catalog_revision: str,
    mutation_kind: str,
) -> str | None:
    if event_store is None:
        raise RuntimeError("OFFER_EVENT_STORE_REQUIRED")
    tenant = _required(tenant_id, field="tenant_id")
    business = _required(business_id, field="business_id")
    product = _required(product_id, field="product_id")
    env = _required(environment, field="environment")
    offer = _required(offer_id, field="offer_id")
    revision = _required(catalog_revision, field="catalog_revision")
    kind = _required(mutation_kind, field="mutation_kind")
    found: list[str] = []
    for event_type in (OFFER_CREATED, OFFER_UPDATED):
        event_id = _event_id(
            tenant_id=tenant,
            business_id=business,
            product_id=product,
            environment=env,
            offer_id=offer,
            catalog_revision=revision,
            mutation_kind=kind,
            event_type=event_type,
        )
        existing = _matches(
            event_store,
            tenant_id=tenant,
            event_type=event_type,
            event_id=event_id,
        )
        if len(existing) > 1:
            raise RuntimeError("OFFER_EVENT_SPINE_DUPLICATE")
        if not existing:
            continue
        _validate_existing(
            existing[0],
            business_id=business,
            product_id=product,
            environment=env,
            offer_id=offer,
            catalog_revision=revision,
            mutation_kind=kind,
        )
        found.append(event_id)
    if len(found) > 1:
        raise RuntimeError("OFFER_EVENT_SPINE_CONFLICT")
    return found[0] if found else None


def project_offer_catalog_event(
    event_store: Any,
    *,
    tenant_id: str,
    business_id: str,
    product_id: str,
    environment: str,
    offer_id: str,
    catalog_revision: str,
    mutation_kind: str,
    created: bool = False,
    decision_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    if event_store is None:
        raise RuntimeError("OFFER_EVENT_STORE_REQUIRED")
    tenant = _required(tenant_id, field="tenant_id")
    business = _required(business_id, field="business_id")
    product = _required(product_id, field="product_id")
    env = _required(environment, field="environment")
    offer = _required(offer_id, field="offer_id")
    revision = _required(catalog_revision, field="catalog_revision")
    kind = _required(mutation_kind, field="mutation_kind")
    existing_event_id = find_offer_catalog_event(
        event_store,
        tenant_id=tenant,
        business_id=business,
        product_id=product,
        environment=env,
        offer_id=offer,
        catalog_revision=revision,
        mutation_kind=kind,
    )
    if existing_event_id is not None:
        return existing_event_id

    event_type = OFFER_CREATED if created else OFFER_UPDATED
    event_id = _event_id(
        tenant_id=tenant,
        business_id=business,
        product_id=product,
        environment=env,
        offer_id=offer,
        catalog_revision=revision,
        mutation_kind=kind,
        event_type=event_type,
    )
    now_ms = int(time.time() * 1000)
    event = {
        "event_id": event_id,
        "tenant_id": tenant,
        "source": "offer_catalog",
        "event_type": event_type,
        "timestamp_ms": now_ms,
        "decision_id": str(decision_id or "").strip() or None,
        "correlation_id": str(correlation_id or "").strip() or None,
        "payload": {
            "schema_version": 1,
            "business_id": business,
            "occurred_at_ms": now_ms,
            "recorded_at_ms": now_ms,
            "product_id": product,
            "environment": env,
            "offer_id": offer,
            "catalog_revision": revision,
            "mutation_kind": kind,
        },
    }
    try:
        append_event_strict(event_store, tenant_id=tenant, event=event)
    except Exception:
        existing = _matches(
            event_store,
            tenant_id=tenant,
            event_type=event_type,
            event_id=event_id,
        )
        if len(existing) != 1:
            raise
        _validate_existing(
            existing[0],
            business_id=business,
            product_id=product,
            environment=env,
            offer_id=offer,
            catalog_revision=revision,
            mutation_kind=kind,
        )
        return event_id

    existing = _matches(
        event_store,
        tenant_id=tenant,
        event_type=event_type,
        event_id=event_id,
    )
    if len(existing) != 1:
        raise RuntimeError("OFFER_EVENT_SPINE_APPEND_NOT_DURABLE")
    _validate_existing(
        existing[0],
        business_id=business,
        product_id=product,
        environment=env,
        offer_id=offer,
        catalog_revision=revision,
        mutation_kind=kind,
    )
    return event_id
