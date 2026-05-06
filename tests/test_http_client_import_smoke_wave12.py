from runtime.effects import http_json, url_with_params


def test_http_client_import_smoke_wave12():
    assert callable(http_json)
    assert url_with_params(url="https://example.test", params={"a": 1}).startswith("https://example.test?")
