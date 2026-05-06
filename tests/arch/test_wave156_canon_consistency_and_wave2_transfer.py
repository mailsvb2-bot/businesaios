from __future__ import annotations

from pathlib import Path

from canon.academic_target_architecture import CANONICAL_LAYER_STACK
from canon.allowed_dependency_graph import ACADEMIC_TARGET_DEPENDENCY_GRAPH
from canon.module_boundaries import ACADEMIC_TARGET_MODULE_BOUNDARIES


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_academic_target_bootstrap_has_no_self_dependency() -> None:
    assert "bootstrap" not in ACADEMIC_TARGET_DEPENDENCY_GRAPH["bootstrap"]
    assert "bootstrap" not in ACADEMIC_TARGET_MODULE_BOUNDARIES["bootstrap"]
    assert set(ACADEMIC_TARGET_DEPENDENCY_GRAPH["bootstrap"]) == set(CANONICAL_LAYER_STACK) - {"bootstrap"}


def test_boot_app_boot_wave2_moves_final_owner_to_bootstrap_package() -> None:
    owner_text = _read("bootstrap/app_boot.py")
    shim_text = _read("boot/app_boot.py")
    assert "CANON_APP_BOOT_FINAL_OWNER = True" in owner_text
    assert "build_app_boot_surface().result" in owner_text
    assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.app_boot_surface"' in shim_text
    assert '_load_attr("bootstrap.app_boot_surface", "build_app_boot_surface")' in shim_text


def test_api_wave2_moves_router_and_health_owners_out_of_interfaces() -> None:
    owner_router = _read("adapters/api/fastapi/router_adapter.py")
    shim_router = _read("interfaces/api/fastapi_router_adapter.py")
    owner_health = _read("entrypoints/api/health_handler.py")
    shim_health = _read("interfaces/api/health_handler.py")
    assert "CANON_API_FASTAPI_ROUTER_FINAL_OWNER = True" in owner_router
    assert "build_runtime_api_bundle(" in owner_router
    assert 'Final owner: adapters.api.fastapi.router_adapter' in shim_router
    assert "from entrypoints.api.health_handler import HealthHandler" in shim_health
    assert "class HealthHandler" in owner_health
