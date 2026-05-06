from __future__ import annotations

from demand_capture.request_parser import RequestParser


def test_request_parser_generates_stable_request_ids_for_same_payload() -> None:
    parser = RequestParser()
    event = {'text': 'Need urgent premium help', 'channel': 'website', 'customer_id': 'c-1'}
    first = parser.parse(event)
    second = parser.parse(event)
    assert first.request_id == second.request_id
    assert first.request_id.startswith('req-')
