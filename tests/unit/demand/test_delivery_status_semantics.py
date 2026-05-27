from routing_execution.delivery_status import (
    delivered_at_ms_for_status,
    normalize_delivery_status,
    persisted_delivery_status,
)


def test_normalize_delivery_status_preserves_intermediate_and_duplicate() -> None:
    assert normalize_delivery_status('accepted') == 'accepted'
    assert normalize_delivery_status('queued') == 'queued'
    assert normalize_delivery_status('duplicate') == 'duplicate'
    assert normalize_delivery_status('ok') == 'delivered'


def test_delivered_timestamp_only_exists_for_terminal_delivery() -> None:
    assert delivered_at_ms_for_status('delivered', now_ms=123) == 123
    assert delivered_at_ms_for_status('ok', now_ms=456) == 456
    assert delivered_at_ms_for_status('accepted', now_ms=789) is None
    assert delivered_at_ms_for_status('queued', now_ms=789) is None


def test_persisted_delivery_status_is_manual_review_when_delivery_missing() -> None:
    assert persisted_delivery_status(None, delivery_missing=True) == 'manual_review'
    assert persisted_delivery_status('duplicate') == 'duplicate'
