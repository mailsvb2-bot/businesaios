from types import SimpleNamespace

import boot as boot_pkg
import boot.public_api as public_api


def test_boot_package_boot_application_uses_app_boot_surface(monkeypatch) -> None:
    sentinel = object()

    def fake_loader(module_name: str, attr_name: str):
        assert (module_name, attr_name) == ("bootstrap.app_boot_surface", "build_app_boot_surface")
        return lambda *args, **kwargs: SimpleNamespace(result=sentinel)

    monkeypatch.setattr(boot_pkg, "_load_attr", fake_loader)

    assert boot_pkg.boot_application() is sentinel
    assert public_api.boot_application() is sentinel


def test_boot_package_boot_http_app_uses_http_boot_surface(monkeypatch) -> None:
    sentinel = object()

    def fake_loader(module_name: str, attr_name: str):
        assert (module_name, attr_name) == ("bootstrap.http_boot_surface", "build_http_boot_surface")
        return lambda *args, **kwargs: SimpleNamespace(http_app=sentinel)

    monkeypatch.setattr(boot_pkg, "_load_attr", fake_loader)

    assert boot_pkg.boot_http_app() is sentinel
    assert public_api.boot_http_app() is sentinel


def test_boot_package_build_runtime_uses_runtime_bootstrap_owner(monkeypatch) -> None:
    sentinel = object()

    def fake_loader(module_name: str, attr_name: str):
        assert (module_name, attr_name) == ("bootstrap.compose", "build_runtime")
        return lambda *args, **kwargs: sentinel

    monkeypatch.setattr(boot_pkg, "_load_attr", fake_loader)

    assert boot_pkg.build_runtime() is sentinel
    assert public_api.build_runtime() is sentinel
