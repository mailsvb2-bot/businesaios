from __future__ import annotations

import importlib.util
import json
import os

from runtime.platform.postgres_migration_runner import apply_postgres_migrations, migration_files
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "postgres_migrations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "required", "enabled"}


def _dsn() -> str:
    return str(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()


def _enabled() -> bool:
    return str(os.getenv("POSTGRES_RUNTIME_ENABLED") or os.getenv("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _proof_required() -> bool:
    return _truthy_env("POSTGRES_LIVE_PROOF_REQUIRED") or _truthy_env("PRODUCTION_BOOT_PROOF_REQUIRED")


def run() -> tuple[bool, str]:
    files = [path.name for path in migration_files()]
    dsn = _dsn()
    enabled = _enabled()
    required = _proof_required()
    psycopg_available = importlib.util.find_spec("psycopg") is not None
    if not dsn and not enabled:
        payload = {
            "artifact": "postgres_migrations",
            "status": "blocked" if required else "advisory_only",
            "migration_files": files,
            "applied": [],
            "skipped": files if not required else [],
            "warnings": [] if required else ["postgres_runtime_not_declared"],
            "violations": ["postgres_migrations_real_database_required"] if required else [],
            "proof_required": required,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        if required:
            return False, "postgres migrations blocked: postgres_migrations_real_database_required"
        return True, "postgres migrations artifact written: artifacts/ci/postgres_migrations.json status=advisory_only"
    if not dsn or not enabled or not psycopg_available:
        violations = []
        if not dsn:
            violations.append("database_url_required")
        if not enabled:
            violations.append("postgres_enablement_required")
        if not psycopg_available:
            violations.append("psycopg_runtime_required")
        payload = {
            "artifact": "postgres_migrations",
            "status": "blocked",
            "migration_files": files,
            "applied": [],
            "skipped": [],
            "violations": violations,
            "proof_required": required,
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, "postgres migrations blocked: " + ",".join(violations)
    try:
        results = apply_postgres_migrations(dsn)
    except Exception as exc:
        payload = {
            "artifact": "postgres_migrations",
            "status": "blocked",
            "migration_files": files,
            "applied": [],
            "skipped": [],
            "violations": ["postgres_migration_failed"],
            "proof_required": required,
            "error": f"{type(exc).__name__}: {exc}",
            "claims_production_ready": False,
        }
        _write_artifact(payload)
        return False, "postgres migrations failed: " + str(exc)
    payload = {
        "artifact": "postgres_migrations",
        "status": "ready",
        "migration_files": files,
        "applied": [item.migration_file for item in results if item.applied],
        "skipped": [item.migration_file for item in results if not item.applied],
        "violations": [],
        "proof_required": required,
        "claims_production_ready": False,
    }
    _write_artifact(payload)
    return True, "postgres migrations ready: artifacts/ci/postgres_migrations.json"


__all__ = ["run"]
