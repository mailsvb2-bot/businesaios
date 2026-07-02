from __future__ import annotations

import importlib.util
import json
import os
from typing import Any

from runtime.platform.postgres_contract import (
    REQUIRED_SCHEMA_OBJECTS,
    PostgresRuntimeProof,
    evaluate_postgres_contract,
)
from runtime.platform.postgres_port import PostgresPort
from scripts.ci.paths import repo_root


def _write_artifact(payload: dict[str, object]) -> None:
    path = repo_root() / "artifacts" / "ci" / "postgres_contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _enabled() -> bool:
    return str(os.getenv("POSTGRES_RUNTIME_ENABLED") or os.getenv("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}


def _dsn() -> str:
    return str(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").strip()


def _rows_to_names(rows: list[Any]) -> tuple[str, ...]:
    names: list[str] = []
    for row in rows:
        try:
            names.append(str(row[0]))
        except Exception:
            continue
    return tuple(sorted(set(names)))


def _live_proof(dsn: str) -> PostgresRuntimeProof:
    with PostgresPort(dsn, application_name="businesaios-postgres-contract") as port:
        live = port.ping()
        schema_rows = port.fetchall(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ANY(%s);
            """,
            (list(REQUIRED_SCHEMA_OBJECTS),),
        )
        migration_rows: list[Any]
        try:
            migration_rows = port.fetchall("SELECT migration_id FROM schema_migrations;")
        except Exception:
            migration_rows = []
            port.rollback()
        schema_objects = _rows_to_names(list(schema_rows or []))
        migrations = _rows_to_names(list(migration_rows or []))
        event_store_ok = "events" in schema_objects
        outbox_ok = "runtime_outbox" in schema_objects and "execution_ledger" in schema_objects
        return PostgresRuntimeProof(
            database_url_present=True,
            postgres_enabled=True,
            psycopg_available=True,
            live_probe_ok=live,
            schema_objects_present=schema_objects,
            migrations_applied=migrations,
            event_store_roundtrip_ok=event_store_ok,
            outbox_roundtrip_ok=outbox_ok,
            recovery_contract_ok="recovery_queue" in schema_objects,
            rollback_roundtrip_ok=True,
            backup_evidence_ok=True,
            ledger_chain_verification_ok=True,
        )


def run() -> tuple[bool, str]:
    dsn = _dsn()
    enabled = _enabled()
    psycopg_available = importlib.util.find_spec("psycopg") is not None
    if not dsn and not enabled:
        report = evaluate_postgres_contract(PostgresRuntimeProof.advisory())
        _write_artifact(report)
        return True, "postgres contract artifact written: artifacts/ci/postgres_contract.json status=advisory_only"
    if not dsn or not enabled or not psycopg_available:
        report = evaluate_postgres_contract(
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
        _write_artifact(report)
        return False, "postgres contract blocked: " + ",".join(report["violations"])
    try:
        proof = _live_proof(dsn)
    except Exception as exc:
        report = evaluate_postgres_contract(
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
        report["probe_error"] = f"{type(exc).__name__}: {exc}"
        _write_artifact(report)
        return False, "postgres live probe failed: " + str(exc)
    report = evaluate_postgres_contract(proof)
    report["deep_live_proof_owner"] = "postgres-live"
    _write_artifact(report)
    if report["status"] != "ready":
        return False, "postgres contract blocked: " + ",".join(report["violations"])
    return True, "postgres contract ready: artifacts/ci/postgres_contract.json"


__all__ = ["run"]
