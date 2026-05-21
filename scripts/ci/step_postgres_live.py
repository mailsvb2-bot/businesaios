from __future__ import annotations

import importlib.util
import json
import os

from runtime.platform.postgres_contract import PostgresRuntimeProof, evaluate_postgres_contract
from runtime.platform.postgres_live_probe import PostgresLiveProbeConfig, run_postgres_live_probe
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "postgres_live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _dsn() -> str:
    return str(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()


def _enabled() -> bool:
    return str(os.getenv("POSTGRES_RUNTIME_ENABLED") or os.getenv("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _apply_migrations() -> bool:
    return str(os.getenv("POSTGRES_APPLY_MIGRATIONS") or os.getenv("RUN_MIGRATIONS_BEFORE_START") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def run() -> tuple[bool, str]:
    dsn = _dsn()
    enabled = _enabled()
    psycopg_available = importlib.util.find_spec("psycopg") is not None
    if not dsn and not enabled:
        payload = evaluate_postgres_contract(PostgresRuntimeProof.advisory())
        payload["artifact"] = "postgres_live"
        payload["status"] = "advisory_only"
        payload["live_runtime_probe"] = False
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
        _write_artifact(payload)
        return False, "postgres live blocked: " + ",".join(payload["violations"])
    try:
        payload = run_postgres_live_probe(
            PostgresLiveProbeConfig(
                dsn=dsn,
                apply_migrations=_apply_migrations(),
                proof_id=os.getenv("POSTGRES_LIVE_PROOF_ID", "ci-postgres-live-proof"),
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
        payload["probe_error"] = f"{type(exc).__name__}: {exc}"
        _write_artifact(payload)
        return False, "postgres live probe failed: " + str(exc)
    payload["artifact"] = "postgres_live"
    payload["live_runtime_probe"] = True
    _write_artifact(payload)
    if payload["status"] != "ready":
        return False, "postgres live blocked: " + ",".join(payload["violations"])
    return True, "postgres live ready: artifacts/ci/postgres_live.json"


__all__ = ["run"]
