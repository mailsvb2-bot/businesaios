from __future__ import annotations

import pytest

from application.campaign.event_promotion import EventPromotionTarget, event_advertising_url


def test_event_advertising_url_keeps_event_identity_and_attribution() -> None:
    target = EventPromotionTarget(
        event_id="event-123",
        public_slug="webinar/demo",
        public_base_url="https://business.example.test",
    )
    url = event_advertising_url(target)
    assert url == (
        "https://business.example.test/e/webinar%2Fdemo"
        "?source=ads&campaign_ref=event%3Aevent-123"
    )
    assert "/clientplatform/acquire" not in url


@pytest.mark.parametrize(
    ("base", "slug"),
    [
        ("http://business.example.test", "event"),
        ("", "event"),
        ("https://business.example.test?unsafe=1", "event"),
        ("https://business.example.test", ""),
    ],
)
def test_event_advertising_url_fails_closed(base: str, slug: str) -> None:
    with pytest.raises(ValueError):
        EventPromotionTarget(
            event_id="event-123",
            public_slug=slug,
            public_base_url=base,
        )
