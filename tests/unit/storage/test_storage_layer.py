from __future__ import annotations

import pytest

from datetime import UTC, datetime, timedelta

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
            scope="execution",
            run_id="run-1",
            action_type="publish",
            verification_status="verified",
            refs=("ev:1",),
            payload={"status": "ok"},
            created_at=now - timedelta(days=40),
            retention_until=now - timedelta(days=1),
        )
    )
    preserved = store.append(
        EvidenceRecord(
            tenant_id="tenant-a",
            scope="execution",
            run_id="run-2",
            action_type="publish",
            verification_status="verified",
            refs=("ev:2",),
            payload={"status": "ok"},
            created_at=now,
            retention_until=now + timedelta(days=30),
            legal_hold=True,
        )
    )
    runner = StorageRetentionJobRunner(evidence_store=store)
    report = runner.run(now=now)
    assert report.evidence_deleted == 1
    assert store.get(expired.evidence_id) is None
    assert store.get(preserved.evidence_id) is not None


def test_schema_version_store_round_trip(tmp_path) -> None:
    store = SqliteSchemaVersionStore(SqliteSessionFactory(tmp_path / "schema.db"))
    record = store.upsert(
        SchemaVersionRecord(
            scope="storage",
            component="audit_store",
            tenant_id="tenant-a",
            version=3,
            details={"migration": "v3"},
        )
    )
    assert record.fingerprint
    fetched = store.get(scope="storage", component="audit_store", tenant_id="tenant-a")
    assert fetched is not None
    assert fetched.version == 3
    assert store.current_version(scope="storage", component="audit_store", tenant_id="tenant-a") == 3


def test_retention_policy_requires_aware_datetime() -> None:
    policy = RetentionPolicy(audit_retention_days=7, evidence_retention_days=8)
    base = datetime.now(UTC)
    assert policy.retention_until_for_audit(created_at=base) > base
    assert policy.retention_until_for_evidence(created_at=base) > base
