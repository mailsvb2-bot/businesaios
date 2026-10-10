from __future__ import annotations

import pytest

from application.campaign.registry import EventPromotionTarget, event_advertising_url


def test_event_advertising_url_targets_existing_canonical_public_route() -> None:
    target = EventPromotionTarget(
        event_id="event-123",
        tenant_id="tenant-a",
        business_id="business-a",
        public_base_url="https://business.example.test",
    )
    url = event_advertising_url(target)
    assert url == (
        "https://business.example.test/public-site/events/tenant-a/business-a/event-123"
        "?source=ads&campaign_ref=event%3Aevent-123"
    )
    assert "/e/" not in url
    assert "/clientplatform/acquire" not in url


@pytest.mark.parametrize(
    ("base", "tenant_id", "business_id"),
    [
        ("http://business.example.test", "tenant-a", "business-a"),
        ("", "tenant-a", "business-a"),
        ("https://business.example.test?unsafe=1", "tenant-a", "business-a"),
        ("https://business.example.test", "", "business-a"),
        ("https://business.example.test", "tenant-a", ""),
    ],
)
def test_event_advertising_url_fails_closed(base: str, tenant_id: str, business_id: str) -> None:
    with pytest.raises(ValueError):
        EventPromotionTarget(
            event_id="event-123",
            tenant_id=tenant_id,
            business_id=business_id,
            public_base_url=base,
        )
