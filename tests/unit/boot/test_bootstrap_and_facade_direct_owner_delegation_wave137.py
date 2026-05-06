from __future__ import annotations

from boot.facade import get_boot_facade


def test_boot_facade_delegates_directly_to_owner_surfaces(monkeypatch):
    calls: list[str] = []

    class DummyAppSurface:
        result = "app-result"

    class DummyHttpSurface:
        http_app = "http-app"

    class DummyRuntime:
        pass

    def fake_load_attr(module_name: str, attr_name: str):
        calls.append(f"{module_name}:{attr_name}")
        if (module_name, attr_name) == ("bootstrap.app_boot_surface", "build_app_boot_surface"):
            return lambda: DummyAppSurface()
        if (module_name, attr_name) == ("bootstrap.http_boot_surface", "build_http_boot_surface"):
            return lambda: DummyHttpSurface()
        if (module_name, attr_name) == ("bootstrap.compose", "build_runtime"):
            return lambda: "runtime"
        raise AssertionError((module_name, attr_name))

    monkeypatch.setattr("boot.facade._load_attr", fake_load_attr)
    facade = get_boot_facade()

    assert facade.boot_application() == "app-result"
    assert facade.build_app_boot_surface().result == "app-result"
    assert facade.boot_http_app() == "http-app"
    assert facade.build_runtime() == "runtime"
    assert calls == [
        "bootstrap.app_boot_surface:build_app_boot_surface",
        "bootstrap.app_boot_surface:build_app_boot_surface",
        "bootstrap.http_boot_surface:build_http_boot_surface",
        "bootstrap.compose:build_runtime",
    ]
