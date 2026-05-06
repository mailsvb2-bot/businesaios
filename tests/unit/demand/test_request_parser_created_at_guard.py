from __future__ import annotations

from demand_capture.request_parser import RequestParser


def test_request_parser_falls_back_when_created_at_is_invalid() -> None:
    request = RequestParser().parse({'text': 'hello', 'created_at_ms': 'not-a-number'})
    assert request.created_at_ms > 0
