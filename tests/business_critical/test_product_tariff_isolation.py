from __future__ import annotations

from collections.abc import Iterable

import pytest

from core.read_model.cache import global_cache
from core.users.read_model import selected_tariff


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
        event_types: tuple[str, ...] = (),
        user_id: str | None = None,
        **_kwargs,
    ) -> Iterable[dict]:
        allowed = set(event_types)
        if event_type:
            allowed.add(event_type)
        return [
            event
            for event in self.events
            if event["tenant_id"] == tenant_id
            and (user_id is None or event["user_id"] == user_id)
            and (not allowed or event["event_type"] in allowed)
            and int(event.get("timestamp_ms") or 0) >= int(start_ms or 0)
            and (end_ms is None or int(event.get("timestamp_ms") or 0) < int(end_ms))
        ]


def _tariff_event(*, product_id: str, tariff: str, amount: int, timestamp_ms: int) -> dict:
    return {
        "tenant_id": "business-a",
        "user_id": "user-1",
        "event_type": "tariff_selected",
        "timestamp_ms": timestamp_ms,
        "payload": {
            "tenant_id": "business-a",
            "product_id": product_id,
            "tariff": tariff,
            "amount": amount,
            "period": "month",
            "days": 30,
        },
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    global_cache().clear()
    yield
    global_cache().clear()


@pytest.mark.lock
def test_tariff_for_one_product_does_not_replace_another_product_tariff() -> None:
    store = FakeEventStore(
        [
            _tariff_event(
                product_id="crm-pro",
                tariff="CRM Pro",
                amount=900,
                timestamp_ms=100,
            ),
            _tariff_event(
                product_id="hr-pro",
                tariff="HR Basic",
                amount=300,
                timestamp_ms=200,
            ),
        ]
    )

    crm = selected_tariff(
        store,
        tenant_id="business-a",
        product_id="crm-pro",
        user_id="user-1",
    )
    hr = selected_tariff(
        store,
        tenant_id="business-a",
        product_id="hr-pro",
        user_id="user-1",
    )

    assert crm["tariff"] == "CRM Pro"
    assert crm["product_id"] == "crm-pro"
    assert hr["tariff"] == "HR Basic"
    assert hr["product_id"] == "hr-pro"


@pytest.mark.lock
def test_tariff_cache_key_includes_product_scope() -> None:
    store = FakeEventStore(
        [
            _tariff_event(
                product_id="crm-pro",
                tariff="CRM Pro",
                amount=900,
                timestamp_ms=100,
            )
        ]
    )

    assert selected_tariff(
        store,
        tenant_id="business-a",
        product_id="crm-pro",
        user_id="user-1",
    )["tariff"] == "CRM Pro"
    assert selected_tariff(
        store,
        tenant_id="business-a",
        product_id="hr-pro",
        user_id="user-1",
    ) is None
