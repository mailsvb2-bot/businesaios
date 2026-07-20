from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import runtime._internal.market_intelligence.http_transport as transport


def result(**overrides):
    values = {
        "headers": {},
        "error_kind": None,
        "error_message": None,
        "status": 200,
        "text": "",
        "json": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_request_url_and_retry_contracts(monkeypatch):
    captured = {}
    monkeypatch.setattr(transport, "url_with_params", lambda *, url, params: captured.update(url=url, params=params) or "built")
    req = transport.HttpRequest(
        method="GET",
        url="https://example.test/path",
        params={"q": "hello", "many": [1, None, 2], "none": None, "mapping": {"x": 1}},
    )
    assert req.build_url() == "built"
    assert captured["params"] == {"q": "hello", "many": ("1", "2"), "mapping": "{'x': 1}"}

    policy = transport.RetryPolicy(max_attempts=3, base_delay_seconds=2, max_delay_seconds=5)
    assert policy.should_retry(attempt=1, status_code=429, code="x")
    assert policy.should_retry(attempt=1, status_code=None, code="timeout")
    assert not policy.should_retry(attempt=3, status_code=429, code="timeout")
    assert not policy.should_retry(attempt=1, status_code=400, code="invalid_json")
    monkeypatch.setattr(transport.random, "uniform", lambda low, high: high)
    assert policy.sleep_seconds(attempt=1) == pytest.approx(2 + 2 / 3)
    assert policy.sleep_seconds(attempt=4) == 5
    assert policy.sleep_seconds(attempt=1, retry_after_seconds=99) == 5


def test_rate_limit_and_request_validation(monkeypatch):
    state = transport.RateLimitState()
    assert not state.is_blocked()
    monkeypatch.setattr(transport.time, "time", lambda: 10.0)
    state.reset_at = 11.0
    assert state.is_blocked()
    state.reset_at = 9.0
    assert not state.is_blocked()

    client = transport.CanonicalHttpTransport()
    for url, message in [
        ("", "url is required"),
        ("ftp://example.test", "only http/https"),
        ("https://", "url host is required"),
    ]:
        with pytest.raises(transport.HttpTransportError, match=message):
            client.execute("provider", transport.HttpRequest(method="GET", url=url))


def test_perform_success_json_forms_and_body_contract(monkeypatch):
    calls = []
    responses = iter(
        [
            result(status=201, text='{"ok":true}', json=None, headers={"X": "1"}),
            result(status=200, text='[{"id":1},2]', json=None),
            result(status=200, text='42', json=None),
            result(status=204, text="", json=None),
        ]
    )
    monkeypatch.setattr(
        transport,
        "sync_request",
        lambda **kwargs: calls.append(kwargs) or next(responses),
    )
    client = transport.CanonicalHttpTransport()
    first = client.execute(
        " provider ",
        transport.HttpRequest(
            method="POST",
            url="https://example.test",
            params={"q": "x"},
            headers={"X-Test": "yes"},
            body={"a": "б"},
            timeout_seconds=0,
        ),
    )
    assert first.status_code == 201 and first.json_payload == {"ok": True}
    assert calls[0]["method"] == "POST"
    assert calls[0]["timeout_s"] == 1.0
    assert calls[0]["headers"]["Accept"] == "application/json"
    assert calls[0]["headers"]["Content-Type"].startswith("application/json")
    assert calls[0]["body"].decode() == '{"a": "б"}'

    second = client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert second.json_payload == ({"id": 1}, 2)
    third = client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert third.json_payload == 42
    fourth = client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert fourth.json_payload is None

    with pytest.raises(transport.HttpTransportError, match="body not allowed"):
        client._perform(
            transport.HttpRequest(method="DELETE", url="https://example.test", body={"x": 1}),
            "provider",
        )


def test_transport_error_invalid_json_and_default_status(monkeypatch):
    client = transport.CanonicalHttpTransport(retry_policy=transport.RetryPolicy(max_attempts=1))
    monkeypatch.setattr(
        transport,
        "sync_request",
        lambda **kwargs: result(
            error_kind="timeout",
            error_message="slow",
            status=504,
            headers={"retry-after": "2"},
            text="preview",
            json=None,
        ),
    )
    with pytest.raises(transport.HttpTransportError) as exc_info:
        client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert exc_info.value.code == "timeout"
    assert exc_info.value.status_code == 504
    assert exc_info.value.payload["headers"] == {"retry-after": "2"}

    monkeypatch.setattr(transport, "sync_request", lambda **kwargs: result(status=200, text="not-json", json=None))
    with pytest.raises(transport.HttpTransportError) as invalid:
        client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert invalid.value.code == "invalid_json"

    monkeypatch.setattr(transport, "sync_request", lambda **kwargs: result(status=None, text="", json=None))
    response = client.execute(
        "provider",
        transport.HttpRequest(method="GET", url="https://example.test", accept_json=False),
    )
    assert response.status_code == 599


def test_retry_rate_limit_and_case_insensitive_retry_after(monkeypatch):
    calls = []
    sleeps = []
    responses = iter(
        [
            result(status=429, headers={"retry-after": "3"}),
            result(status=200, json={"ok": True}),
        ]
    )
    monkeypatch.setattr(transport, "sync_request", lambda **kwargs: calls.append(kwargs) or next(responses))
    monkeypatch.setattr(transport.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(transport.time, "time", lambda: 100.0)
    client = transport.CanonicalHttpTransport(
        retry_policy=transport.RetryPolicy(max_attempts=2, max_delay_seconds=10)
    )
    response = client.execute(" p ", transport.HttpRequest(method="GET", url="https://example.test"))
    assert response.status_code == 200 and len(calls) == 2
    assert sleeps == [3.0, 3.0]
    assert client._rate_limit["p"].retry_after_seconds == 3.0


def test_retry_after_http_date_and_invalid_values(monkeypatch):
    client = transport.CanonicalHttpTransport()
    monkeypatch.setattr(transport.time, "time", lambda: 1000.0)
    future = datetime.fromtimestamp(1005, tz=UTC)
    assert client._read_retry_after_seconds({"RETRY-AFTER": future.strftime("%a, %d %b %Y %H:%M:%S GMT")}) == 5
    assert client._read_retry_after_seconds({"Retry-After": "-2"}) == 0
    assert client._read_retry_after_seconds({"Retry-After": "invalid"}) is None
    assert client._read_retry_after_seconds({}) is None
    client._update_rate_limit("x", {})
    assert "x" not in client._rate_limit


def test_retry_exhaustion_raises_temporary_unavailable(monkeypatch):
    monkeypatch.setattr(transport, "sync_request", lambda **kwargs: result(status=503, headers={}))
    monkeypatch.setattr(transport.time, "sleep", lambda seconds: None)
    client = transport.CanonicalHttpTransport(retry_policy=transport.RetryPolicy(max_attempts=2, base_delay_seconds=0))
    with pytest.raises(transport.HttpTransportError) as exc_info:
        client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test"))
    assert exc_info.value.code == "temporary_unavailable"
    assert exc_info.value.status_code == 503


def test_transport_exception_retry_and_wait_for_existing_limit(monkeypatch):
    responses = iter([
        result(error_kind="timeout", error_message="slow", status=None, headers={"x": "1", "retry-after": "1"}),
        result(status=200, json={"ok": True}),
    ])
    sleeps = []
    monkeypatch.setattr(transport, "sync_request", lambda **kwargs: next(responses))
    monkeypatch.setattr(transport.time, "time", lambda: 50.0)
    monkeypatch.setattr(transport.time, "sleep", lambda seconds: sleeps.append(seconds))
    client = transport.CanonicalHttpTransport(
        retry_policy=transport.RetryPolicy(max_attempts=2, max_delay_seconds=5)
    )
    assert client.execute("provider", transport.HttpRequest(method="GET", url="https://example.test")).status_code == 200
    assert sleeps == [1.0, 1.0]
    client._rate_limit["blocked"] = transport.RateLimitState(reset_at=52.0)
    client._wait_for_rate_limit("blocked")
    assert sleeps[-1] == 2.0
