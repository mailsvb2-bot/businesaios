from __future__ import annotations

from collections.abc import Iterable

import pytest

from core.payments.read_model import latest_payment_status
from core.read_model.cache import global_cache


class FakeEventStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
        **_kwargs,
    ) -> Iterable[dict]:
        return [
            event
            for event in self.events
            if event["tenant_id"] == tenant_id
            and (user_id is None or event["user_id"] == user_id)
            and (event_type is None or event["event_type"] == event_type)
            and int(event.get("timestamp_ms") or 0) >= int(start_ms or 0)
            and (end_ms is None or int(event.get("timestamp_ms") or 0) < int(end_ms))
        ]


def _payment_event(*, event_type: str, product_id: str, status: str, timestamp_ms: int) -> dict:
    return {
        "tenant_id": "business-a",
        "user_id": "user-1",
        "event_type": event_type,
        "timestamp_ms": timestamp_ms,
        "payload": {
            "external_id": f"payment-{product_id}",
            "status": status,
            "metadata": {
                "tenant_id": "business-a",
                "product_id": product_id,
                "order_id": f"order-{product_id}",
            },
        },
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    global_cache().clear()
    yield
    global_cache().clear()


@pytest.mark.lock
def test_payment_for_one_product_does_not_mark_another_product_as_paid() -> None:
    store = FakeEventStore(
        [
            _payment_event(
                event_type="payment_captured",
                product_id="crm-pro",
                status="succeeded",
                timestamp_ms=100,
            ),
            _payment_event(
                event_type="payment_failed",
                product_id="hr-pro",
                status="failed",
                timestamp_ms=200,
            ),
        ]
    )

    crm = latest_payment_status(
        event_store=store,
        tenant_id="business-a",
        product_id="crm-pro",
        user_id="user-1",
    )
    hr = latest_payment_status(
        event_store=store,
        tenant_id="business-a",
        product_id="hr-pro",
        user_id="user-1",
    )

    assert crm["status"] == "succeeded"
    assert crm["product_id"] == "crm-pro"
    assert hr["status"] == "failed"
    assert hr["product_id"] == "hr-pro"


@pytest.mark.lock
def test_payment_cache_key_includes_product_scope() -> None:
    store = FakeEventStore(
        [
            _payment_event(
                event_type="payment_captured",
                product_id="crm-pro",
                status="succeeded",
                timestamp_ms=100,
            )
        ]
    )

    assert latest_payment_status(
        event_store=store,
        tenant_id="business-a",
        product_id="crm-pro",
        user_id="user-1",
    )["status"] == "succeeded"
    assert latest_payment_status(
        event_store=store,
        tenant_id="business-a",
        product_id="hr-pro",
        user_id="user-1",
    ) == {"status": "none", "product_id": "hr-pro"}
