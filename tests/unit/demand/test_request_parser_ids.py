from demand_capture.request_parser import RequestParser


def test_request_id_changes_across_distinct_timestamps_when_no_explicit_id() -> None:
    parser = RequestParser()
    first = parser.parse({"customer_id": "c1", "channel": "telegram", "text": "need help", "created_at_ms": 1000})
    second = parser.parse({"customer_id": "c1", "channel": "telegram", "text": "need help", "created_at_ms": 2000})
    assert first.request_id != second.request_id


def test_request_id_stays_explicit_when_request_id_is_provided() -> None:
    parser = RequestParser()
    request = parser.parse({"request_id": "req-123", "customer_id": "c1", "channel": "telegram", "text": "need help"})
    assert request.request_id == "req-123"
