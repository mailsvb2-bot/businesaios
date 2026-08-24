from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from entrypoints.api.fastapi_app_factory import _api_cors_allowed_origins, _configure_browser_cors

STAGING_UI_ORIGIN = "https://app.businessaios.ru"


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/public-site/cta/start",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )


def test_default_staging_ui_origin_gets_credentialed_cors(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("API_CORS_ALLOWED_ORIGINS", raising=False)
    app = FastAPI()
    _configure_browser_cors(app)
    client = TestClient(app)

    response = _preflight(client, STAGING_UI_ORIGIN)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == STAGING_UI_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()
    assert "origin" in response.headers["vary"].lower()


def test_default_staging_ui_origin_gets_cors_on_simple_get(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("API_CORS_ALLOWED_ORIGINS", raising=False)
    app = FastAPI()

    @app.get("/public-site/integrations")
    def integrations():
        return {"ok": True}

    _configure_browser_cors(app)
    client = TestClient(app)

    response = client.get("/public-site/integrations", headers={"Origin": STAGING_UI_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == STAGING_UI_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_untrusted_browser_origin_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("API_CORS_ALLOWED_ORIGINS", raising=False)
    app = FastAPI()
    _configure_browser_cors(app)
    client = TestClient(app)

    response = _preflight(client, "https://evil.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_policy_rejects_wildcard_configuration(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("API_CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValueError, match="must not use wildcards"):
        _api_cors_allowed_origins()


def test_cors_policy_rejects_insecure_production_origin(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("API_CORS_ALLOWED_ORIGINS", "http://app.businessaios.ru")

    with pytest.raises(ValueError, match="must use https"):
        _api_cors_allowed_origins()


def test_explicit_origin_list_is_exact_and_deduplicated(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv(
        "API_CORS_ALLOWED_ORIGINS",
        "https://app.businessaios.ru, http://localhost:5173,https://app.businessaios.ru/",
    )

    assert _api_cors_allowed_origins() == (STAGING_UI_ORIGIN, "http://localhost:5173")
