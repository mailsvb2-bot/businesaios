from __future__ import annotations

from collections.abc import Iterable

import pytest

from core.entitlements.read_model import compute_entitlements
from core.payments.read_model import latest_payment_status
from core.read_model.cache import global_cache
from core.users.read_model import selected_product, selected_tariff, user_settings


class FakeTenantEventStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def _matching(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_types: tuple[str, ...] = (),
        event_type: str | None = None,
    ) -> list[dict]:
        allowed = set(event_types)
        if event_type:
            allowed.add(str(event_type))
        rows = [
            event
            for event in self.events
            if str(event.get("tenant_id")) == str(tenant_id)
            and (user_id is None or str(event.get("user_id")) == str(user_id))
            and (not allowed or str(event.get("event_type")) in allowed)
        ]
        return sorted(rows, key=lambda event: int(event.get("timestamp_ms") or 0))

    def latest_event(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_types: tuple[str, ...] = (),
        event_type: str | None = None,
        **_kwargs,
    ) -> dict | None:
        rows = self._matching(
            tenant_id=tenant_id,
            user_id=user_id,
            event_types=event_types,
            event_type=event_type,
        )
        return rows[-1] if rows else None

    def latest_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_types: tuple[str, ...] = (),
        event_type: str | None = None,
        limit: int = 100,
        **_kwargs,
    ) -> Iterable[dict]:
        rows = self._matching(
            tenant_id=tenant_id,
            user_id=user_id,
            event_types=event_types,
            event_type=event_type,
        )
        return list(reversed(rows[-int(limit) :]))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
        event_types: tuple[str, ...] = (),
        user_id: str | None = None,
        **_kwargs,
    ) -> Iterable[dict]:
        return [
            event
            for event in self._matching(
                tenant_id=tenant_id,
                user_id=user_id,
                event_types=event_types,
                event_type=event_type,
            )
            if int(event.get("timestamp_ms") or 0) >= int(start_ms or 0)
            and (end_ms is None or int(event.get("timestamp_ms") or 0) < int(end_ms))
        ]


def _event(*, tenant: str, event_type: str, payload: dict) -> dict:
    return {
        "tenant_id": tenant,
        "user_id": "same-external-user",
        "event_type": event_type,
        "timestamp_ms": 100,
        "payload": dict(payload),
    }


@pytest.fixture(autouse=True)
def _clear_read_model_cache() -> Iterable[None]:
    global_cache().clear()
    yield
    global_cache().clear()


@pytest.mark.lock
def test_same_external_user_id_cannot_leak_settings_or_tariff_across_businesses() -> None:
    store = FakeTenantEventStore(
        [
            _event(tenant="business-a", event_type="user_setting_set", payload={"key": "city", "value": "Berlin"}),
            _event(tenant="business-b", event_type="user_setting_set", payload={"key": "city", "value": "Tokyo"}),
            _event(tenant="business-a", event_type="tariff_selected", payload={"tariff": "A-Pro", "amount": 100}),
            _event(tenant="business-b", event_type="tariff_selected", payload={"tariff": "B-Pro", "amount": 900}),
        ]
    )

    assert user_settings(store, tenant_id="business-a", user_id="same-external-user")["city"] == "Berlin"
    assert user_settings(store, tenant_id="business-b", user_id="same-external-user")["city"] == "Tokyo"
    assert selected_tariff(store, tenant_id="business-a", user_id="same-external-user")["tariff"] == "A-Pro"
    assert selected_tariff(store, tenant_id="business-b", user_id="same-external-user")["tariff"] == "B-Pro"


@pytest.mark.lock
def test_same_external_user_id_cannot_leak_product_payment_or_entitlement_across_businesses() -> None:
    store = FakeTenantEventStore(
        [
            _event(tenant="business-a", event_type="product_selected@v1", payload={"product_id": "product-a"}),
            _event(tenant="business-b", event_type="product_selected@v1", payload={"product_id": "product-b"}),
            _event(tenant="business-a", event_type="payment_captured", payload={"external_id": "pay-a", "status": "succeeded"}),
            _event(tenant="business-b", event_type="payment_failed", payload={"external_id": "pay-b", "status": "failed"}),
            _event(tenant="business-a", event_type="entitlement_granted", payload={"product_id": "product-a", "full_access": True}),
        ]
    )

    assert selected_product(store, tenant_id="business-a", user_id="same-external-user")["product_id"] == "product-a"
    assert selected_product(store, tenant_id="business-b", user_id="same-external-user")["product_id"] == "product-b"
    assert latest_payment_status(event_store=store, tenant_id="business-a", user_id="same-external-user")["status"] == "succeeded"
    assert latest_payment_status(event_store=store, tenant_id="business-b", user_id="same-external-user")["status"] == "failed"
    assert compute_entitlements(event_store=store, tenant_id="business-a", user_id="same-external-user")["full_access"] is True
    assert compute_entitlements(event_store=store, tenant_id="business-b", user_id="same-external-user")["full_access"] is False
