from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_boot_runtime_support_cluster_has_bootstrap_final_owners() -> None:
    final_owner_paths = [
        "bootstrap/runtime_boot_guard.py",
        "bootstrap/runtime_boot_manifest.py",
        "bootstrap/runtime_boot_report.py",
        "bootstrap/runtime_dependency_sets.py",
        "bootstrap/runtime_manifest_support.py",
        "bootstrap/runtime_service_specs.py",
    ]
    for relpath in final_owner_paths:
        text = _read(relpath)
        assert "FINAL_OWNER = True" in text or "SINGLE_SOURCE = True" in text

    boot_root = _read("boot/__init__.py")
    shims = [
        ("runtime_boot_guard", "bootstrap.runtime_boot_guard"),
        ("runtime_boot_manifest", "bootstrap.runtime_boot_manifest"),
        ("runtime_boot_report", "bootstrap.runtime_boot_report"),
        ("runtime_dependency_sets", "bootstrap.runtime_dependency_sets"),
        ("runtime_manifest_support", "bootstrap.runtime_manifest_support"),
        ("runtime_service_specs", "bootstrap.runtime_service_specs"),
    ]
    for alias_name, owner in shims:
        assert f'"{alias_name}": "{owner}"' in boot_root


def test_fastapi_and_entrypoint_cluster_have_final_owners() -> None:
    assert "CANON_API_HEADLESS_ROUTE_HANDLERS_FINAL_OWNER = True" in _read("entrypoints/api/headless_route_handlers.py")
    assert "CANON_API_GOVERNANCE_ROUTE_HANDLERS_FINAL_OWNER = True" in _read("entrypoints/api/governance_route_handlers.py")
    assert "CANON_API_METRICS_ROUTE_HANDLERS_FINAL_OWNER = True" in _read("entrypoints/api/metrics_route_handlers.py")
    assert "CANON_FASTAPI_DEPENDENCIES_FINAL_OWNER = True" in _read("adapters/api/fastapi/dependencies.py")
    assert "CANON_FASTAPI_ROUTER_SUPPORT_FINAL_OWNER = True" in _read("adapters/api/fastapi/router_support.py")
    assert "CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER = True" in _read("adapters/api/fastapi/public_routes.py")
    assert "CANON_FASTAPI_CONTROL_PLANE_ROUTES_FINAL_OWNER = True" in _read("adapters/api/fastapi/control_plane_routes.py")


def test_router_and_factory_consume_final_owner_surfaces() -> None:
    router = _read("adapters/api/fastapi/router_adapter.py")
    factory = _read("entrypoints/api/fastapi_app_factory.py")
    assert "from adapters.api.fastapi.dependencies import FastAPIDependencyContainer" in router
    assert "from adapters.api.fastapi.public_routes import register_public_api_routes" in router
    assert "from adapters.api.fastapi.control_plane_routes import register_control_plane_routes" in router
    assert "from adapters.api.fastapi.router_support import build_auth_bundle, build_webhook_verifier, resolve_metrics, tenant_registry_has_records" in router
    assert "from entrypoints.api.governance_route_handlers import GovernanceRouteHandlers" in router
    assert "from entrypoints.api.metrics_route_handlers import MetricsRouteHandlers" in router
    assert "from adapters.api.fastapi.dependencies import FastAPIDependencyContainer" in factory
    assert "from adapters.api.fastapi.exception_handlers import register_exception_handlers" in factory
    assert "from adapters.api.fastapi.router_adapter import create_api_router" in factory
