from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from storage import (
    AuditRecord,
    EvidenceRecord,
    RetentionPolicy,
    SqliteAuditStore,
    SqliteEvidenceStore,
    SqliteSchemaVersionStore,
    SqliteSession,
    SqliteSessionFactory,
    StorageRetentionJobRunner,
)
from storage.schema_version_store import SchemaVersionRecord
from storage.tenant_partitioning import build_partition_key, describe_tenant_partition, normalize_storage_tenant_id


def test_tenant_partitioning_normalizes_global() -> None:
    assert normalize_storage_tenant_id("") == "global"
    assert build_partition_key(None, scope="audit") == "audit:global"
    partition = describe_tenant_partition(None, scope="evidence")
    assert partition.partition_suffix == "global"
    assert partition.postgres_schema.startswith("tenant_")


def test_sqlite_session_exposes_explicit_transaction_contract(tmp_path) -> None:
    db_path = tmp_path / "contract.db"
    with SqliteSession(db_path) as session:
        session.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        session.execute("INSERT INTO items(value) VALUES (?)", ("committed",))
        session.commit()

    with SqliteSession(db_path) as session:
        assert session.fetchone("SELECT value FROM items WHERE id = ?", (1,))["value"] == "committed"
        session.execute("INSERT INTO items(value) VALUES (?)", ("rolled-back",))
        session.rollback()
        rows = session.fetchall("SELECT value FROM items ORDER BY id")
        assert [row["value"] for row in rows] == ["committed"]


def test_sqlite_session_is_forbidden_in_prod_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("BUSINESAIOS_ALLOW_TEST_SQLITE_FALLBACK", "0")
    with pytest.raises(RuntimeError, match="SQLITE_FALLBACK_FORBIDDEN_IN_PROD"):
        with SqliteSession(tmp_path / "prod.db"):
            raise AssertionError("sqlite fallback must not open in prod")


def test_sqlite_audit_store_round_trip(tmp_path) -> None:
    store = SqliteAuditStore(SqliteSessionFactory(tmp_path / "audit.db"))
    now = datetime.now(UTC)
    record = store.append(
        AuditRecord(
            tenant_id="tenant-a",
            scope="control_plane",
            actor="operator",
            action="approve",
            entity_type="request",
            entity_id="req-1",
            payload={"ok": True},
            created_at=now,
            retention_until=now + timedelta(days=30),
        )
    )
    fetched = store.get(record.event_id)
    assert fetched is not None
    assert fetched.tenant_id == "tenant-a"
    assert fetched.payload["ok"] is True
    items = store.list_for_tenant(tenant_id="tenant-a")
    assert len(items) == 1
    assert items[0].partition_key == "audit_control_plane:tenant-a"


def test_sqlite_evidence_store_round_trip_and_retention(tmp_path) -> None:
    store = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "evidence.db"))
    now = datetime.now(UTC)
    expired = store.append(
        EvidenceRecord(
            tenant_id="tenant-a",
            subject="decision",
            evidence_type="trace",
            payload={"score": 0.9},
            created_at=now - timedelta(days=90),
            retention_until=now - timedelta(days=1),
        )
    )
    active = store.append(
        EvidenceRecord(
            tenant_id="tenant-a",
            subject="decision",
            evidence_type="trace",
            payload={"score": 1.0},
            created_at=now,
            retention_until=now + timedelta(days=30),
        )
    )
    assert store.get(active.evidence_id).payload["score"] == 1.0
    assert len(store.list_for_tenant(tenant_id="tenant-a")) == 2
    runner = StorageRetentionJobRunner(evidence_store=store)
    result = runner.run(now=now)
    assert result.deleted_evidence_ids == (expired.evidence_id,)
    assert store.get(expired.evidence_id) is None
    assert store.get(active.evidence_id) is not None


def test_schema_version_store_round_trip(tmp_path) -> None:
    store = SqliteSchemaVersionStore(SqliteSessionFactory(tmp_path / "schema.db"))
    record = SchemaVersionRecord(
        component="audit",
        version="v1",
        checksum="abc",
        applied_at=datetime.now(UTC),
    )
    store.set(record)
    fetched = store.get("audit")
    assert fetched == record
    assert store.list_all() == (record,)
