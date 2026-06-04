from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from scripts.ci.paths import reports_dir

REQUIRED_HTTP_PATHS = ("/readyz", "/storagez", "/executionz")


def _write_artifact(payload: dict[str, object]) -> None:
    path = reports_dir() / "boot_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _safe_path_part(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip())
    return clean or "unknown"


def _boot_smoke_root() -> Path:
    explicit = os.environ.get("BAIOS_BOOT_SMOKE_ROOT")
    if explicit:
        return Path(explicit)

    if os.environ.get("GITHUB_ACTIONS") == "true":
        parts = (
            os.environ.get("GITHUB_RUN_ID", "run"),
            os.environ.get("GITHUB_RUN_ATTEMPT", "attempt"),
            os.environ.get("GITHUB_JOB", "job"),
            str(os.getpid()),
        )
        suffix = "-".join(_safe_path_part(part) for part in parts)
        return Path("/tmp") / "businesaios-boot-smoke" / suffix

    return Path("/tmp") / "businesaios-boot-smoke"


def _prepare_boot_smoke_env() -> None:
    """Keep the smoke deterministic without changing production semantics."""

    root = _boot_smoke_root()

    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    os.environ.setdefault("APP_PROFILE", "api")
    os.environ.setdefault("ENV", "ci")
    os.environ.setdefault("RUN_MODE", "demo")
    os.environ.setdefault("DATA_DIR", str(root / "data" / "ci-demo-tenant"))
    os.environ.setdefault("RUNTIME_DIR", str(root / "runtime"))


def _route_paths(app: object) -> set[str]:
    routes = getattr(app, "routes", ())
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
    return paths


def _json_or_text(response: Any) -> object:
    content_type = str(response.headers.get("content-type", ""))
    if content_type.startswith("application/json"):
        return response.json()
    return str(response.text)[:500]


def _probe_http_app(app: object) -> tuple[dict[str, object], list[str]]:
    client = TestClient(app)
    probes: dict[str, object] = {}
    violations: list[str] = []
    for path in REQUIRED_HTTP_PATHS:
        response = client.get(path)
        body = _json_or_text(response)
        probes[path] = {
            "status_code": response.status_code,
            "body": body,
        }
        if response.status_code != 200:
            violations.append(f"http_probe_failed:{path}:{response.status_code}")
            continue
        if isinstance(body, dict):
            status = str(body.get("status") or "").strip().lower()
            if status in {"error", "failed"}:
                violations.append(f"http_probe_unhealthy:{path}:{status}")
    return probes, violations


def _dependency_set_summary(dependency_sets: object) -> dict[str, object]:
    if not isinstance(dependency_sets, dict):
        return {"count": 0, "names": [], "total_edges": 0}
    return {
        "count": len(dependency_sets),
        "names": sorted(str(name) for name in dependency_sets),
        "total_edges": sum(len(tuple(deps or ())) for deps in dependency_sets.values()),
    }


def run() -> tuple[bool, str]:
    _prepare_boot_smoke_env()
    try:
        from boot.runtime_boot_manifest import RUNTIME_BOOT_MANIFEST
        from boot.runtime_dependency_sets import RUNTIME_DEPENDENCY_SETS
        from boot.runtime_service_specs import RUNTIME_SERVICE_SPECS
        from bootstrap.http_boot_surface import build_http_boot_surface
        from bootstrap.system_boot_surface import build_system_boot_surface

        system_surface = build_system_boot_surface()
        http_surface = build_http_boot_surface(system_surface=system_surface)
        paths = _route_paths(http_surface.http_app)
        missing_paths = sorted(set(REQUIRED_HTTP_PATHS) - paths)
        probes, probe_violations = _probe_http_app(http_surface.http_app)
        violations = [*(f"missing_http_path:{path}" for path in missing_paths), *probe_violations]
        payload = {
            "artifact": "boot_smoke",
            "status": "ready" if not violations else "blocked",
            "system_surface_type": type(system_surface).__name__,
            "http_surface_type": type(http_surface).__name__,
            "http_app_type": type(http_surface.http_app).__name__,
            "runtime_manifest_entries": len(RUNTIME_BOOT_MANIFEST),
            "runtime_dependency_sets": _dependency_set_summary(RUNTIME_DEPENDENCY_SETS),
            "runtime_service_specs": len(RUNTIME_SERVICE_SPECS),
            "required_http_paths": list(REQUIRED_HTTP_PATHS),
            "registered_http_paths": sorted(paths),
            "missing_http_paths": missing_paths,
            "http_probes": probes,
            "violations": violations,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        if violations:
            return False, "boot smoke blocked: " + ",".join(violations)
        return True, "boot smoke passed: system/http surfaces built and readiness endpoints responded"
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
