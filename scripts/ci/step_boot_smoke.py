from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.paths import reports_dir


def _write_artifact(payload: dict[str, object]) -> None:
    path = reports_dir() / "boot_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _route_paths(app: object) -> set[str]:
    routes = getattr(app, "routes", ())
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
    return paths


def run() -> tuple[bool, str]:
    try:
        from bootstrap.system_boot_surface import build_system_boot_surface
        from bootstrap.http_boot_surface import build_http_boot_surface
        from boot.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST
        from boot.runtime_dependency_sets import RUNTIME_DEPENDENCY_SETS
        from boot.runtime_service_specs import RUNTIME_SERVICE_SPECS

        system_surface = build_system_boot_surface()
        http_surface = build_http_boot_surface(system_surface=system_surface)
        paths = _route_paths(http_surface.http_app)
        required_paths = {"/readyz", "/storagez", "/executionz"}
        missing_paths = sorted(required_paths - paths)
        payload = {
            "artifact": "boot_smoke",
            "status": "ready" if not missing_paths else "blocked",
            "system_surface_type": type(system_surface).__name__,
            "http_surface_type": type(http_surface).__name__,
            "http_app_type": type(http_surface.http_app).__name__,
            "runtime_manifest_entries": len(RUNTIME_BOOT_MANIFEST),
            "runtime_dependency_sets": sorted(RUNTIME_DEPENDENCY_SETS),
            "runtime_service_specs": len(RUNTIME_SERVICE_SPECS),
            "required_http_paths": sorted(required_paths),
            "missing_http_paths": missing_paths,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        if missing_paths:
            return False, "boot smoke blocked: missing paths=" + ",".join(missing_paths)
        return True, "boot smoke passed: system/http surfaces built and readiness paths registered"
    except Exception as exc:
        payload = {
            "artifact": "boot_smoke",
            "status": "blocked",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, f"boot smoke failed: {type(exc).__name__}: {exc}"


__all__ = ["run"]