from __future__ import annotations

from entrypoints.api.fastapi_app_factory import _api_docs_enabled
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard


def test_api_docs_default_off_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)

    assert _api_docs_enabled() is False


def test_api_docs_can_be_explicitly_enabled_outside_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)

    assert _api_docs_enabled() is True


def test_transport_encryption_evidence_requires_explicit_signal() -> None:
    context = RequestContext(metadata={})

    assert ApiSecuritySurfaceGuard._transport_encrypted(request_context=context) is False


def test_transport_encryption_evidence_accepts_https_scheme() -> None:
    context = RequestContext(metadata={"scheme": "https"})

    assert ApiSecuritySurfaceGuard._transport_encrypted(request_context=context) is True


def test_transport_encryption_evidence_rejects_http_scheme() -> None:
    context = RequestContext(metadata={"scheme": "http"})

    assert ApiSecuritySurfaceGuard._transport_encrypted(request_context=context) is False
