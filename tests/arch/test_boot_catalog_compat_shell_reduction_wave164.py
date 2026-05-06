from __future__ import annotations

import importlib
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_boot_factory_root_uses_private_catalog_owner() -> None:
    text = _read("boot/factories/__init__.py")
    assert "boot.factories._catalog_owner" in text
    assert "boot.factories.catalog" not in text
    assert not Path("boot/factories/catalog.py").exists()


def test_boot_registration_root_uses_private_catalog_owner() -> None:
    text = _read("boot/registrations/__init__.py")
    assert "boot.registrations._catalog_owner" in text
    assert "boot.registrations.catalog" not in text


def test_boot_registration_catalog_alias_lives_on_package_owned_module() -> None:
    owner = importlib.import_module("boot.registrations")
    alias = importlib.import_module("boot.registrations.catalog")
    assert getattr(alias, "register_architecture_watch") is getattr(owner, "register_architecture_watch")
    assert not Path("boot/registrations/catalog.py").exists()
