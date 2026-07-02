from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from runtime.platform.postgres_contract import PostgresRuntimeProof, evaluate_postgres_contract
from runtime.platform.postgres_live_probe import PostgresLiveProbeConfig, run_postgres_live_probe
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "postgres_live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "required", "enabled"}


def _dsn() -> str:
    return str(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()


def _enabled() -> bool:
    return str(os.getenv("POSTGRES_RUNTIME_ENABLED") or os.getenv("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _proof_required() -> bool:
    return _truthy_env("POSTGRES_LIVE_PROOF_REQUIRED")


def _apply_migrations() -> bool:
    return str(os.getenv("POSTGRES_APPLY_MIGRATIONS") or os.getenv("RUN_MIGRATIONS_BEFORE_START") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _backup_evidence_ok() -> bool:
    if _truthy_env("POSTGRES_BACKUP_EVIDENCE_OK"):
        return True
    raw_path = str(os.getenv("POSTGRES_BACKUP_EVIDENCE_PATH") or "").strip()
    if not raw_path:
        return False
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root() / candidate
    return candidate.exists() and candidate.is_file()


def _block_required_postgres_live(*, dsn: str, enabled: bool, psycopg_available: bool) -> tuple[bool, str]:
    payload = evaluate_postgres_contract(
        PostgresRuntimeProof(
            database_url_present=bool(dsn),
            postgres_enabled=enabled,
            psycopg_available=psycopg_available,
            live_probe_ok=False,
            schema_objects_present=(),
            migrations_applied=(),
            event_store_roundtrip_ok=False,
            outbox_roundtrip_ok=False,
            recovery_contract_ok=False,
        )
    )
    violations = set(payload.get("violations") or ())
    violations.add("postgres_live_real_probe_required")
    if not dsn:
        violations.add("postgres_live_database_url_required")
    if not enabled:
        violations.add("postgres_live_enablement_required")
    if not psycopg_available:
        violations.add("postgres_live_psycopg_required")
    payload["artifact"] = "postgres_live"
    payload["status"] = "blocked"
    payload["violations"] = sorted(violations)
    payload["live_runtime_probe"] = False
    payload["proof_required"] = True
    payload["claims_production_ready"] = False
    _write_artifact(payload)
    return False, "postgres live blocked: " + ",".join(payload["violations"])


def run() -> tuple[bool, str]:
    dsn = _dsn()
    enabled = _enabled()
    required = _proof_required()
    psycopg_available = importlib.util.find_spec("psycopg") is not None
    if not dsn and not enabled:
        if required:
            return _block_required_postgres_live(dsn=dsn, enabled=enabled, psycopg_available=psycopg_available)
        payload = evaluate_postgres_contract(PostgresRuntimeProof.advisory())
        payload["artifact"] = "postgres_live"
        payload["status"] = "advisory_only"
        payload["live_runtime_probe"] = False
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return True, "postgres live artifact written: artifacts/ci/postgres_live.json status=advisory_only"
    if not dsn or not enabled or not psycopg_available:
        payload = evaluate_postgres_contract(
            PostgresRuntimeProof(
                database_url_present=bool(dsn),
                postgres_enabled=enabled,
                psycopg_available=psycopg_available,
                live_probe_ok=False,
                schema_objects_present=(),
                migrations_applied=(),
                event_store_roundtrip_ok=False,
                outbox_roundtrip_ok=False,
                recovery_contract_ok=False,
            )
        )
        payload["artifact"] = "postgres_live"
        payload["live_runtime_probe"] = False
        payload["proof_required"] = required
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return False, "postgres live blocked: " + ",".join(payload["violations"])
    try:
        payload = run_postgres_live_probe(
            PostgresLiveProbeConfig(
                dsn=dsn,
                apply_migrations=_apply_migrations(),
                proof_id=os.getenv("POSTGRES_LIVE_PROOF_ID", "ci-postgres-live-proof"),
                backup_evidence_ok=_backup_evidence_ok(),
            )
        )
    except Exception as exc:
        payload = evaluate_postgres_contract(
            PostgresRuntimeProof(
                database_url_present=True,
                postgres_enabled=True,
                psycopg_available=psycopg_available,
                live_probe_ok=False,
                schema_objects_present=(),
                migrations_applied=(),
                event_store_roundtrip_ok=False,
                outbox_roundtrip_ok=False,
                recovery_contract_ok=False,
            )
        )
        payload["artifact"] = "postgres_live"
        payload["live_runtime_probe"] = False
        payload["proof_required"] = required
        payload["probe_error"] = f"{type(exc).__name__}: {exc}"
        payload["claims_production_ready"] = False
        _write_artifact(payload)
        return False, "postgres live probe failed: " + str(exc)
    payload["artifact"] = "postgres_live"
    payload["live_runtime_probe"] = True
    payload["proof_required"] = required
    payload["claims_production_ready"] = False
    _write_artifact(payload)
    if payload["status"] != "ready":
        return False, "postgres live blocked: " + ",".join(payload["violations"])
    return True, "postgres live ready: artifacts/ci/postgres_live.json"


__all__ = ["run"]
