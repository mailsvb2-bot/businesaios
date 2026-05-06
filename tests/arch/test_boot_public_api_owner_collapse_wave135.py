from pathlib import Path

from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES


def test_boot_public_api_shims_are_marked_collapsed_to_direct_surfaces() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.app_public_api"] == "bootstrap.app_boot_surface"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.http_public_api"] == "bootstrap.http_boot_surface"


def test_app_public_api_delegates_directly_to_app_boot_surface() -> None:
    text = Path("boot/app_public_api.py").read_text(encoding="utf-8")
    assert 'CANON_APP_PUBLIC_API_DIRECT_SURFACE_DELEGATION = True' in text
    assert 'from boot.app_boot import boot_application' not in text
    assert 'from bootstrap.app_boot_surface import build_app_boot_surface as _build_app_boot_surface' in text
    assert 'return _build_app_boot_surface(*args, **kwargs).result' in text


def test_http_public_api_delegates_directly_to_http_boot_surface() -> None:
    text = Path("boot/http_public_api.py").read_text(encoding="utf-8")
    assert 'CANON_HTTP_PUBLIC_API_DIRECT_SURFACE_DELEGATION = True' in text
    assert 'from boot.http_boot import boot_http_app' not in text
    assert 'from bootstrap.http_boot_surface import build_http_boot_surface as _build_http_boot_surface' in text
    assert 'return _build_http_boot_surface(*args, **kwargs).http_app' in text


def test_boot_runtime_collapse_readiness_points_to_bootstrap_owners() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.runtime_orchestrator"] == "bootstrap.compose"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.runtime_public_api"] == "bootstrap.compose"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.bootstrap"] == "bootstrap.compose"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.app_boot"] == "bootstrap.app_boot"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.app_public_api"] == "bootstrap.app_boot_surface"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.http_public_api"] == "bootstrap.http_boot_surface"
