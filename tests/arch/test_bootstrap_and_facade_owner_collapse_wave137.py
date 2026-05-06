from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_bootstrap_surface_stays_thin_without_owner_cycle() -> None:
    text = _read("boot/bootstrap.py")
    assert 'CANON_BOOTSTRAP_DELEGATES_TO_BOOTSTRAP_COMPOSE = True' in text
    assert '_load_attr("bootstrap.compose", "bootstrap")' in text
    assert '_load_attr("bootstrap.compose", "get_bootstrapped_runtime")' in text
    assert 'boot.runtime_boot' not in text


def test_boot_facade_delegates_straight_to_owner_surfaces() -> None:
    text = _read("boot/facade.py")
    assert 'CANON_BOOT_FACADE_DIRECT_OWNER_DELEGATION = True' in text
    assert 'boot.app_public_api' not in text
    assert 'boot.http_public_api' not in text
    assert 'boot.runtime_public_api' not in text
    assert 'bootstrap.app_boot_surface' in text
    assert 'bootstrap.http_boot_surface' in text
    assert 'runtime.bootstrap.sovereign_bootstrap' not in text
    assert 'runtime.bootstrap' in text
