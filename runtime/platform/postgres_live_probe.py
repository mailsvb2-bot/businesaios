from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runtime.execution.crash_window_recovery_contract import ExecutionCrashWindowState, required_recovery_action
from runtime.platform.postgres_contract import (
    REQUIRED_SCHEMA_OBJECTS,
    PostgresRuntimeProof,
    evaluate_postgres_contract,
)
from runtime.platform.postgres_port import PostgresPort


@dataclass(frozen=True)
class PostgresLiveProbeConfig:
    dsn: str
    apply_migrations: bool = False
    tenant_id: str = "ci-postgres-live-tenant"
    proof_id: str = "ci-postgres-live-proof"
    backup_evidence_ok: bool = False


def _migration_path() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations" / "postgres" / "0001_runtime_core.sql"


def _apply_migrations(port: PostgresPort) -> None:
    port.execute(_migration_path().read_text(encoding="utf-8"))
    port.commit()


def _rows_to_names(rows: object) -> tuple[str, ...]:
    names: list[str] = []
    for row in rows or []:  # type: ignore[assignment]
        try:
            names.append(str(row[0]))
        except Exception:
            continue
    return tuple(sorted(set(names)))


def _schema_objects(port: PostgresPort) -> tuple[str, ...]:
    rows = port.fetchall(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s);
        """,
        (list(REQUIRED_SCHEMA_OBJECTS),),
    )
    return _rows_to_names(rows)


def _migrations(port: PostgresPort) -> tuple[str, ...]:
    try:
        rows = port.fetchall("SELECT migration_id FROM schema_migrations;")
        return _rows_to_names(rows)
    except Exception:
        port.rollback()
        return ()


def _event_store_roundtrip(port: PostgresPort, *, tenant_id: str, proof_id: str) -> bool:
    event_id = f"pg-live-event-{proof_id}"
    port.execute(
        """
        INSERT INTO events (event_id, tenant_id, user_id, source, event_type, timestamp_ms, decision_id, correlation_id, payload_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (event_id) DO NOTHING;
        """,
        (
            event_id,
            tenant_id,
            "system",
            "postgres_live_probe",
            "PostgresLiveProbeEvent",
            1,
            f"decision-{proof_id}",
            f"corr-{proof_id}",
            json.dumps({"proof_id": proof_id}, sort_keys=True),
        ),
    )
    port.commit()
    row = port.fetchone("SELECT payload_json FROM events WHERE event_id = %s AND tenant_id = %s;", (event_id, tenant_id))
    if not row:
        return False
    return json.loads(row[0] or "{}").get("proof_id") == proof_id


def _outbox_roundtrip(port: PostgresPort, *, tenant_id: str, proof_id: str) -> bool:
    outbox_id = f"pg-live-outbox-{proof_id}"
    idem = f"pg-live-idem-{proof_id}"
    port.execute(
        """
        INSERT INTO runtime_outbox (outbox_id, tenant_id, idempotency_key, status, payload_json)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (outbox_id) DO NOTHING;
        """,
        (outbox_id, tenant_id, idem, "pending", json.dumps({"proof_id": proof_id}, sort_keys=True)),
    )
    port.execute(
        """
        UPDATE runtime_outbox
        SET status = 'claimed', claimed_at = NOW(), updated_at = NOW()
        WHERE outbox_id = %s AND status IN ('pending', 'claimed');
        """,
        (outbox_id,),
    )
    port.execute(
        """
        UPDATE runtime_outbox
        SET status = 'verified', dispatched_at = COALESCE(dispatched_at, NOW()), verified_at = NOW(), updated_at = NOW()
        WHERE outbox_id = %s AND status = 'claimed';
        """,
        (outbox_id,),
    )
    port.commit()
    row = port.fetchone("SELECT status FROM runtime_outbox WHERE outbox_id = %s;", (outbox_id,))
    return bool(row and row[0] == "verified")


def _recovery_roundtrip(port: PostgresPort, *, tenant_id: str, proof_id: str) -> bool:
    ledger_id = f"pg-live-ledger-{proof_id}"
    recovery_id = f"pg-live-recovery-{proof_id}"
    action = required_recovery_action(
        ExecutionCrashWindowState(
            decision_id=f"decision-{proof_id}",
            idempotency_key=f"recovery-idem-{proof_id}",
            ledger_marked=True,
            dispatch_claimed=False,
            handler_dispatched=False,
            effect_verified=False,
        )
    ).value
    port.execute(
        """
        INSERT INTO execution_ledger (ledger_id, tenant_id, decision_id, idempotency_key, ledger_marked, dispatch_claimed, handler_dispatched, effect_verified)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (ledger_id) DO NOTHING;
        """,
        (ledger_id, tenant_id, f"decision-{proof_id}", f"recovery-idem-{proof_id}", True, False, False, False),
    )
    port.execute(
        """
        INSERT INTO recovery_queue (recovery_id, tenant_id, ledger_id, required_action, status, payload_json)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (recovery_id) DO NOTHING;
        """,
        (recovery_id, tenant_id, ledger_id, action, "pending", json.dumps({"proof_id": proof_id}, sort_keys=True)),
    )
    port.commit()
    row = port.fetchone("SELECT required_action, status FROM recovery_queue WHERE recovery_id = %s;", (recovery_id,))
    return bool(row and row[0] == "replay_dispatch" and row[1] == "pending")


def _rollback_roundtrip(port: PostgresPort, *, tenant_id: str, proof_id: str) -> bool:
    snapshot_id = f"pg-live-rollback-{proof_id}"
    port.execute(
        "DELETE FROM runtime_snapshots WHERE snapshot_id = %s;",
        (snapshot_id,),
    )
    port.commit()
    port.execute(
        """
        INSERT INTO runtime_snapshots (snapshot_id, tenant_id, snapshot_type, payload_json)
        VALUES (%s,%s,%s,%s);
        """,
        (snapshot_id, tenant_id, "rollback_probe", json.dumps({"proof_id": proof_id}, sort_keys=True)),
    )
    port.rollback()
    row = port.fetchone("SELECT snapshot_id FROM runtime_snapshots WHERE snapshot_id = %s;", (snapshot_id,))
    return row is None


def _ledger_chain_verification(port: PostgresPort, *, tenant_id: str, proof_id: str) -> bool:
    ledger_id = f"pg-live-chain-{proof_id}"
    idempotency_key = f"pg-live-chain-idem-{proof_id}"
    port.execute(
        """
        INSERT INTO execution_ledger (ledger_id, tenant_id, decision_id, idempotency_key, ledger_marked, dispatch_claimed, handler_dispatched, effect_verified)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (ledger_id) DO UPDATE SET
          ledger_marked = EXCLUDED.ledger_marked,
          dispatch_claimed = FALSE,
          handler_dispatched = FALSE,
          effect_verified = FALSE,
          updated_at = NOW();
        """,
        (ledger_id, tenant_id, f"decision-chain-{proof_id}", idempotency_key, True, False, False, False),
    )
    port.execute("UPDATE execution_ledger SET dispatch_claimed = TRUE, updated_at = NOW() WHERE ledger_id = %s AND ledger_marked = TRUE;", (ledger_id,))
    port.execute("UPDATE execution_ledger SET handler_dispatched = TRUE, updated_at = NOW() WHERE ledger_id = %s AND dispatch_claimed = TRUE;", (ledger_id,))
    port.execute("UPDATE execution_ledger SET effect_verified = TRUE, updated_at = NOW() WHERE ledger_id = %s AND handler_dispatched = TRUE;", (ledger_id,))
    port.commit()
    row = port.fetchone(
        """
        SELECT ledger_marked, dispatch_claimed, handler_dispatched, effect_verified
        FROM execution_ledger WHERE ledger_id = %s AND tenant_id = %s;
        """,
        (ledger_id, tenant_id),
    )
    return bool(row and tuple(row) == (True, True, True, True))


def run_postgres_live_probe(config: PostgresLiveProbeConfig) -> dict[str, object]:
    with PostgresPort(config.dsn, application_name="businesaios-postgres-live") as port:
        if config.apply_migrations:
            _apply_migrations(port)
        live_ok = port.ping()
        schema = _schema_objects(port)
        migrations = _migrations(port)
        event_ok = _event_store_roundtrip(port, tenant_id=config.tenant_id, proof_id=config.proof_id) if "events" in schema else False
        outbox_ok = _outbox_roundtrip(port, tenant_id=config.tenant_id, proof_id=config.proof_id) if "runtime_outbox" in schema else False
        recovery_ok = _recovery_roundtrip(port, tenant_id=config.tenant_id, proof_id=config.proof_id) if "recovery_queue" in schema else False
        rollback_ok = _rollback_roundtrip(port, tenant_id=config.tenant_id, proof_id=config.proof_id) if "runtime_snapshots" in schema else False
        ledger_chain_ok = _ledger_chain_verification(port, tenant_id=config.tenant_id, proof_id=config.proof_id) if "execution_ledger" in schema else False
    proof = PostgresRuntimeProof(
        database_url_present=True,
        postgres_enabled=True,
        psycopg_available=True,
        live_probe_ok=live_ok,
        schema_objects_present=schema,
        migrations_applied=migrations,
        event_store_roundtrip_ok=event_ok,
        outbox_roundtrip_ok=outbox_ok,
        recovery_contract_ok=recovery_ok,
        rollback_roundtrip_ok=rollback_ok,
        backup_evidence_ok=config.backup_evidence_ok,
        ledger_chain_verification_ok=ledger_chain_ok,
    )
    return evaluate_postgres_contract(proof)


__all__ = ["PostgresLiveProbeConfig", "run_postgres_live_probe"]
