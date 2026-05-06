from __future__ import annotations

import asyncio

import pytest

from runtime._internal.effects_clients.http_client import http_json
from runtime._internal.http_transport import HTTPResponse, sync_get
from runtime._internal.llm_transport import llm_post_json
from runtime.finance.event_publisher import FinanceEventPublisher
from runtime.recovery import _iter_recoverable_items


class _AsyncTransport:
    async def get_json(self, **kwargs):
        return HTTPResponse(status=200, json={"ok": True, "url": kwargs["url"]}, text="")

    async def post_json(self, **kwargs):
        return HTTPResponse(status=200, json={"ok": True, "url": kwargs["url"]}, text="")


def test_http_json_supports_nested_event_loop() -> None:
    async def _run() -> dict:
        return http_json("GET", "https://example.com", None, transport=_AsyncTransport())

    assert asyncio.run(_run())["ok"] is True


def test_http_json_rejects_blank_url() -> None:
    with pytest.raises(ValueError, match="url_required"):
        http_json("GET", "", None, transport=_AsyncTransport())


def test_sync_get_rejects_relative_url() -> None:
    response = sync_get(url="/relative", headers={}, params=None, timeout_s=1)
    assert response.status == 599


def test_llm_transport_fails_closed_on_non_2xx(monkeypatch) -> None:
    import runtime._internal.llm_transport as module

    monkeypatch.setattr(module, "sync_post_json", lambda **kwargs: HTTPResponse(status=401, json={"error": "bad"}, text='{"error":"bad"}'))
    with pytest.raises(RuntimeError, match="llm_transport_failed"):
        llm_post_json(provider="anthropic", url="https://example.com", api_key="k", payload={})


def test_recovery_global_scan_is_fail_closed() -> None:
    class _Outbox:
        def list_claimable_all(self, *, limit: int):
            raise RuntimeError("boom")

    assert tuple(_iter_recoverable_items(outbox=_Outbox(), limit=10)) == ()


def test_finance_event_publisher_requires_ids_and_keeps_subscriber() -> None:
    publisher = FinanceEventPublisher()
    seen = []

    def flaky(event):
        seen.append(event.event_name)
        raise RuntimeError("transient")

    publisher.subscribe(flaky)
    publisher.publish("alpha", correlation_id="c1", tenant_id="t1", payload={})
    publisher.publish("beta", correlation_id="c2", tenant_id="t1", payload={})
    assert seen == ["alpha", "beta"]

    with pytest.raises(ValueError, match="event_name_required"):
        publisher.publish("", correlation_id="c3", tenant_id="t1", payload={})
