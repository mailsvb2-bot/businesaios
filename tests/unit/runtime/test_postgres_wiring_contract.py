from __future__ import annotations

from pathlib import Path

from runtime.wiring import StorageConfig, describe_storage_readiness


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_postgres_runtime_wiring_explicitly_enables_event_store() -> None:
    """Regression lock: prod postgres boot must not hit declared-absence mode."""
    source = _read_repo_file("runtime/wiring.py")

    assert "PostgresEventStore(storage.postgres_dsn, enabled=True)" in source
    assert "PostgresEventStore(storage.postgres_dsn)" not in source


def test_postgres_event_store_uses_postgres_ddl_and_canonical_event_id() -> None:
    """Regression lock: postgres adapter must not contain sqlite-only DDL."""
    source = _read_repo_file("runtime/platform/event_store/postgres_event_store.py")

    assert "AUTOINCREMENT" not in source.upper()
    assert "event_id TEXT PRIMARY KEY" in source
    assert "normalize_append_event" in source
    assert "ORDER BY timestamp_ms DESC, event_id DESC" in source


def test_postgres_payment_outbox_claim_uses_update_returning_not_status_probe() -> None:
    """Regression lock: only the worker that changed the row may own the claim."""
    source = _read_repo_file("runtime/platform/outbox/postgres_payment_outbox.py")

    assert "RETURNING id" in source
    assert "WHERE id=%s AND status='pending'" in source
    assert "SELECT status FROM payment_outbox WHERE id=%s" not in source
    assert "_reap_stale_inflight" in source


def test_postgres_runtime_outbox_claim_and_enqueue_report_real_row_changes() -> None:
    """Regression lock: claim/enqueue success must come from UPDATE/INSERT ownership."""
    source = _read_repo_file("runtime/platform/outbox/postgres_outbox.py")

    assert "ON CONFLICT (decision_id) DO NOTHING\n            RETURNING decision_id" in source
    assert "UPDATE outbox SET status='delivering', claimed_at_ms=%s" in source
    assert "RETURNING decision_id" in source
    assert "SELECT status, claimed_at_ms FROM outbox WHERE decision_id=%s" not in source
    assert "int(row[1] or 0) == now" not in source


def test_postgres_ledger_does_not_issue_manual_begin_inside_port_transaction() -> None:
    """Regression lock: PostgresPort already owns transaction boundaries."""
    source = _read_repo_file("runtime/platform/ledger/postgres_ledger.py")

    assert 'execute("BEGIN;' not in source
    assert "self._port.commit()" in source
    assert "self._port.rollback()" in source
    assert "INSERT INTO executed (" in source
    assert "INSERT INTO executed_chain" in source


def test_postgres_ledger_serializes_hash_chain_head_updates() -> None:
    """Regression lock: concurrent workers must not read the same chain head."""
    source = _read_repo_file("runtime/platform/ledger/postgres_ledger.py")

    assert "LEDGER_CHAIN_ADVISORY_LOCK_KEY" in source
    assert "pg_advisory_xact_lock(hashtext(%s))" in source
    assert "_lock_chain_for_transaction()" in source
    assert source.index("self._lock_chain_for_transaction()") < source.index("SELECT entry_hash FROM executed_chain")


def test_postgres_session_is_a_postgres_port_wrapper_not_a_second_driver_surface() -> None:
    """Regression lock: storage session must stay a typed wrapper over PostgresPort."""
    source = _read_repo_file("storage/postgres_session.py")

    assert "from runtime.platform.postgres_port import PostgresPort" in source
    assert "PostgresPort(self._dsn" in source
    assert "import psycopg" not in source
    assert "return {name: value for name, value in zip(names, row)}" in source


def test_postgres_archive_and_snapshot_use_mapping_rows_from_session() -> None:
    """Regression lock: PostgresSession.fetchone returns dict-like rows."""
    archive = _read_repo_file("observability/platform/decision_archive/postgres_decision_archive.py")
    snapshot = _read_repo_file("observability/platform/snapshot_store/postgres_snapshot_store.py")

    assert 'row.get("envelope_json")' in archive
    assert 'row.get("canonical_bytes")' in snapshot
    assert "row[0]" not in archive
    assert "row[0]" not in snapshot
    assert "PostgresSessionFactory" in archive
    assert "PostgresSessionFactory" in snapshot


def test_storage_readiness_reports_prod_postgres_blockers_without_side_effects() -> None:
    readiness = describe_storage_readiness(StorageConfig(env="prod", backend="sqlite", postgres_dsn=None))

    assert readiness["surface"] == "runtime.storage.wiring"
    assert readiness["canonical_owner"] == "runtime.wiring"
    assert readiness["storage_only"] is True
    assert readiness["decision_logic"] is False
    assert readiness["live_ready"] is False
    assert "PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:sqlite" in readiness["blockers"]
    assert "PROD_REQUIRES_POSTGRES_DSN" in readiness["blockers"]


def test_storage_readiness_reports_postgres_roles_when_configured() -> None:
    readiness = describe_storage_readiness(
        StorageConfig(env="prod", backend="postgres", postgres_dsn="postgresql://example.invalid/db")
    )

    assert readiness["live_ready"] is True
    assert readiness["postgres_dsn_configured"] is True
    assert readiness["blockers"] == []
    assert readiness["roles"] == [
        "event_store",
        "ledger",
        "snapshot_store",
        "decision_archive",
        "outbox",
        "payment_outbox",
    ]
