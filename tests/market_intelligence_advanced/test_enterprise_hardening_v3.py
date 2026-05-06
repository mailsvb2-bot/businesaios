from pathlib import Path

from contracts.platforms.market_intelligence_advanced_contract import ProviderCursor
from execution.market_intelligence_data_quality import DataQualityGuard
from runtime._internal.market_intelligence.cursor_store import FileProviderCursorStore
from runtime._internal.market_intelligence.http_transport import CanonicalHttpTransport, HttpRequest, HttpTransportError


def test_http_request_build_url_supports_repeated_query_params():
    req = HttpRequest(method="GET", url="https://example.com/search", params={"tag": ["a", "b"], "q": "x"})
    built = req.build_url()
    assert "tag=a" in built and "tag=b" in built and "q=x" in built


def test_transport_updates_rate_limit_for_provider_on_http_error(monkeypatch):
    transport = CanonicalHttpTransport()

    def _boom(req, provider_key):
        raise HttpTransportError("http_error", "boom", status_code=429, payload={"headers": {"Retry-After": "1"}})

    monkeypatch.setattr(transport, "_perform", _boom)
    try:
        transport.execute("alpha", HttpRequest(method="GET", url="https://example.com"))
    except HttpTransportError:
        pass
    assert transport._rate_limit.get("alpha") is not None


def test_cursor_store_load_is_fail_closed_on_malformed_payload(tmp_path: Path):
    store = FileProviderCursorStore(root_dir=tmp_path)
    bad_path = tmp_path / "tenant" / "alpha.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text('{"tenant_id": "t1", "provider": "p"}', encoding="utf-8")
    cursor = store.load(tenant_id="t1", provider="p", source_family="f", scope_key="s")
    assert isinstance(cursor, ProviderCursor)
    assert cursor.scope_key == "s"


def test_data_quality_drops_repeated_character_spam():
    rows, report = DataQualityGuard().process([{"title": "aaaaaa", "description": "aaaaaa"}])
    assert rows == ()
    assert report.dropped_noise == 1
