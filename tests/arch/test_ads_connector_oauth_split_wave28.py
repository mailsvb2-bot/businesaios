from pathlib import Path


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_ads_connectors_delegate_oauth_and_disconnect_helpers() -> None:
    helper_text = _text("interfaces/ads/connector_oauth_helpers.py")
    assert "resolve_oauth_client_id" in helper_text
    assert "disconnect_tokens_compat" in helper_text

    for path in [
        "interfaces/ads/google_ads_connector.py",
        "interfaces/ads/meta_connector.py",
        "interfaces/ads/tiktok_ads_connector.py",
    ]:
        text = _text(path)
        assert "from .connector_oauth_helpers import" in text
        assert "disconnect_tokens_compat(" in text

    google = _text("interfaces/ads/google_ads_connector.py")
    tiktok = _text("interfaces/ads/tiktok_ads_connector.py")
    meta = _text("interfaces/ads/meta_connector.py")
    assert "resolve_oauth_scope(" in google
    assert "resolve_oauth_scope(" in tiktok
    assert "resolve_oauth_client_id(" in meta
