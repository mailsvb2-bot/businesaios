from __future__ import annotations

from pathlib import Path


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
