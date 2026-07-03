from __future__ import annotations

import pytest

from adapters.api.fastapi.router_support import enforce_control_plane_auth_prod_contract


def test_prod_control_plane_auth_requires_runtime_secret_material(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "file")
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_PATH", "/tmp/control-plane-keys.json")

    with pytest.raises(RuntimeError):
        enforce_control_plane_auth_prod_contract(env_name="prod", pepper="")


def test_prod_control_plane_auth_rejects_memory_store(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "memory")
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_PATH", "/tmp/control-plane-keys.json")

    with pytest.raises(RuntimeError):
        enforce_control_plane_auth_prod_contract(env_name="prod", pepper="runtime-pepper")


def test_prod_control_plane_auth_requires_store_path(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "file")
    monkeypatch.delenv("BUSINESAIOS_API_KEY_STORE_PATH", raising=False)

    with pytest.raises(RuntimeError):
        enforce_control_plane_auth_prod_contract(env_name="prod", pepper="runtime-pepper")


def test_dev_control_plane_auth_keeps_lightweight_defaults(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_API_KEY_STORE_BACKEND", "memory")
    monkeypatch.delenv("BUSINESAIOS_API_KEY_STORE_PATH", raising=False)

    enforce_control_plane_auth_prod_contract(env_name="dev", pepper="")
