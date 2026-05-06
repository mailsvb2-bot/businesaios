from __future__ import annotations

import boot.app_public_api as app_public_api
import boot.http_public_api as http_public_api
import bootstrap.app_boot_surface as app_boot_surface
import bootstrap.http_boot_surface as http_boot_surface


class _FakeAppSurface:
    def __init__(self) -> None:
        self.result = {"ok": True}


class _FakeHttpSurface:
    def __init__(self, http_app) -> None:
        self.http_app = http_app


def test_app_public_api_boot_application_delegates_to_surface(monkeypatch) -> None:
    monkeypatch.setattr(app_boot_surface, "build_app_boot_surface", lambda *args, **kwargs: _FakeAppSurface())
    assert app_public_api.boot_application() == {"ok": True}


def test_http_public_api_boot_http_app_delegates_to_surface(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(http_boot_surface, "build_http_boot_surface", lambda *args, **kwargs: _FakeHttpSurface(sentinel))
    assert http_public_api.boot_http_app() is sentinel
