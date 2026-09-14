from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256

import pytest

from storage.distributed_evidence_audit_backend import DistributedEvidenceStore
from storage.evidence_store import (
    EVIDENCE_LINEAGE_STAGES,
    EvidenceRecord,
    InMemoryEvidenceStore,
    PostgresEvidenceStore,
    SqliteEvidenceStore,
)
from storage.migration_registry import MigrationRegistry, default_storage_migration_registry
from storage.sqlite_fallback import SqliteSessionFactory


def _lineage() -> dict[str, str]:
    return {stage: f"{stage}:ref" for stage in EVIDENCE_LINEAGE_STAGES}


def test_canonical_evidence_contract_round_trips_lineage_and_metadata(tmp_path) -> None:
    now = datetime.now(UTC)
    store = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "canonical-evidence.db"))
    record = store.append(EvidenceRecord(
        tenant_id="tenant-a", scope="decision", run_id="run-1", action_type="send_message",
        verification_status="verified", payload={"value": 42}, source="hubspot", source_type="provider_api",
        business_id="business-a", observed_at=now, confidence=0.91, privacy_class="confidential",
        retention_policy="business_evidence_365d", retention_until=now + timedelta(days=365), lineage=_lineage(),
    ))
    restored = store.get(tenant_id="tenant-a", evidence_id=record.evidence_id)
    assert restored == record.normalized()
    assert restored is not None and restored.lineage_complete
    assert tuple(stage for stage, _ in restored.lineage_path) == EVIDENCE_LINEAGE_STAGES
    assert len(restored.hash) == 64
    same_payload_other_source = EvidenceRecord(
        tenant_id="tenant-a", scope="decision", run_id="run-1", action_type="send_message",
        verification_status="verified", payload={"value": 42}, source="salesforce", source_type="provider_api",
        business_id="business-a", observed_at=now, confidence=0.91, privacy_class="confidential",
        retention_policy="business_evidence_365d", lineage=_lineage(),
    )
    assert same_payload_other_source.payload_sha256 == restored.payload_sha256
    assert same_payload_other_source.hash != restored.hash


def test_unknown_business_and_observed_time_are_not_invented() -> None:
    record = EvidenceRecord.from_legacy(
        tenant_id="tenant-a",
        subject="legacy",
        evidence_type="trace",
        payload={"value": 1},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    ).normalized()
    assert record.business_id == "unknown"
    assert record.observed_at is None
    row = record.to_row()
    assert row["business_id"] == "unknown"
    assert row["observed_at"] is None


def test_evidence_id_is_append_only_and_identical_replay_is_idempotent(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    record = EvidenceRecord(
        evidence_id="evidence-fixed",
        tenant_id="tenant-a",
        scope="provider",
        run_id="run-1",
        action_type="sync",
        verification_status="verified",
        payload={"value": 1},
        source="shopify",
        source_type="provider_api",
        business_id="business-a",
        observed_at=now,
        retention_policy="evidence_30d",
        lineage={"source": "shopify:1", "action": "sync:1", "outcome": "ok:1"},
    )
    memory = InMemoryEvidenceStore()
    assert memory.append(record) == memory.append(record)
    with pytest.raises(ValueError, match="evidence_id is immutable"):
        memory.append(replace(record, payload={"value": 2}))

    sqlite = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "append-only.db"))
    assert sqlite.append(record) == sqlite.append(record)
    with pytest.raises(ValueError, match="evidence_id is immutable"):
        sqlite.append(replace(record, source="forged"))
    assert sqlite.get(tenant_id="tenant-a", evidence_id=record.evidence_id) == record.normalized()


def test_canonical_hash_normalizes_equivalent_timezone_offsets() -> None:
    utc_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    plus_three = utc_time.astimezone(__import__("datetime").timezone(timedelta(hours=3)))
    base = EvidenceRecord(
        evidence_id="timezone-evidence", tenant_id="tenant-a", scope="decision", run_id="run-1",
        action_type="observe", verification_status="verified", payload={"value": 1},
        source="crm", source_type="provider_api", business_id="business-a", observed_at=utc_time,
        created_at=utc_time, retention_until=utc_time + timedelta(days=1), retention_policy="evidence_1d",
    )
    shifted = replace(
        base, observed_at=plus_three, created_at=plus_three,
        retention_until=plus_three + timedelta(days=1),
    )
    assert shifted.normalized() == base.normalized()
    assert shifted.hash == base.hash


def test_canonical_hash_binds_tenant_and_execution_identity() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    base = EvidenceRecord(
        evidence_id="evidence-fixed",
        tenant_id="tenant-a",
        scope="decision",
        run_id="run-1",
        action_id="action-1",
        action_type="send_message",
        verification_status="verified",
        payload={"value": 1},
        source="crm",
        source_type="provider_api",
        business_id="business-a",
        observed_at=now,
        retention_policy="evidence_30d",
    )
    assert replace(base, tenant_id="tenant-b").hash != base.hash
    assert replace(base, run_id="run-2").hash != base.hash
    assert replace(base, action_id="action-2").hash != base.hash
    assert replace(base, verification_status="rejected").hash != base.hash



class _DistributedEvidencePort:
    def __init__(self, rows):
        self.rows = list(rows)

    def append(self, *, partition_key, payload):
        self.rows.append(dict(payload))
        return str(payload.get("evidence_id") or "")

    def read_partition(self, *, partition_key, limit=100, cursor=None):
        return tuple(self.rows[:limit]), None

    def read_prefix(self, *, prefix, limit=100, cursor=None):
        return tuple(self.rows[:limit]), None


def test_distributed_store_has_narrow_legacy_adapter_but_rejects_explicit_downgrade() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    legacy = EvidenceRecord.from_legacy(
        tenant_id="tenant-a", subject="legacy", evidence_type="trace",
        payload={"value": 1}, created_at=created, evidence_id="legacy-dist",
    )
    row = legacy.to_row()
    row.pop("evidence_schema_version")
    row.pop("evidence_sha256")
    records, _ = DistributedEvidenceStore(_DistributedEvidencePort([row])).list_for_tenant(tenant_id="tenant-a")
    assert len(records) == 1
    assert records[0].schema_version == 2
    assert records[0].business_id == "unknown"
    assert records[0].observed_at is None

    downgraded = legacy.to_row()
    downgraded["evidence_schema_version"] = 1
    downgraded["evidence_sha256"] = ""
    with pytest.raises(ValueError, match="legacy evidence schema requires controlled migration"):
        DistributedEvidenceStore(_DistributedEvidencePort([downgraded])).list_for_tenant(tenant_id="tenant-a")

def test_persisted_evidence_with_missing_tenant_fails_closed() -> None:
    record = EvidenceRecord(
        evidence_id="tenant-bound-evidence", tenant_id="tenant-a", scope="decision", run_id="run-1",
        action_type="trace", verification_status="verified", payload={"value": 1},
        source="crm", source_type="provider_api", business_id="business-a",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    row = record.to_row()
    row["tenant_id"] = ""
    row["partition_key"] = "evidence_decision:global"
    with pytest.raises(ValueError, match="tenant_id is required"):
        EvidenceRecord.from_row(row)


def test_evidence_reads_are_tenant_scoped_and_blank_tenant_fails_closed(tmp_path) -> None:
    record = EvidenceRecord(
        evidence_id="tenant-bound-evidence",
        tenant_id="tenant-a",
        scope="decision",
        run_id="run-1",
        action_type="trace",
        verification_status="verified",
        payload={"value": 1},
        source="crm",
        source_type="provider_api",
        business_id="business-a",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    memory = InMemoryEvidenceStore()
    memory.append(record)
    assert memory.get(tenant_id="tenant-a", evidence_id=record.evidence_id) == record.normalized()
    assert memory.get(tenant_id="tenant-b", evidence_id=record.evidence_id) is None
    with pytest.raises(ValueError, match="tenant_id is required"):
        memory.get(tenant_id="", evidence_id=record.evidence_id)

    sqlite = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "tenant-scope.db"))
    sqlite.append(record)
    assert sqlite.get(tenant_id="tenant-a", evidence_id=record.evidence_id) == record.normalized()
    assert sqlite.get(tenant_id="tenant-b", evidence_id=record.evidence_id) is None
    with pytest.raises(ValueError, match="tenant_id is required"):
        sqlite.list_for_tenant(tenant_id="")

    with pytest.raises(ValueError, match="tenant_id is required"):
        replace(record, tenant_id="").normalized()


def test_distributed_store_never_borrows_requested_tenant_for_unscoped_rows() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    scoped = EvidenceRecord.from_legacy(
        tenant_id="tenant-a", subject="legacy", evidence_type="trace",
        payload={"value": 1}, created_at=created, evidence_id="scoped",
    ).to_row()
    unscoped = dict(scoped)
    unscoped["evidence_id"] = "unscoped"
    unscoped.pop("tenant_id")
    other_tenant = dict(scoped)
    other_tenant["evidence_id"] = "other"
    other_tenant["tenant_id"] = "tenant-b"

    records, _ = DistributedEvidenceStore(
        _DistributedEvidencePort([unscoped, other_tenant, scoped])
    ).list_for_tenant(tenant_id="tenant-a")
    assert [item.evidence_id for item in records] == ["scoped"]
    with pytest.raises(ValueError, match="tenant_id is required"):
        DistributedEvidenceStore(_DistributedEvidencePort([scoped])).list_for_tenant(tenant_id="")


class _FakePostgresTenantReadSession:
    dialect = "postgres"

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def fetchone(self, sql, params=None):
        self.calls.append((sql, params))
        return None


class _FakePostgresTenantReadFactory:
    def __init__(self):
        self.session = _FakePostgresTenantReadSession()

    def open(self):
        return self.session


def test_postgres_evidence_get_queries_by_tenant_and_evidence_id() -> None:
    factory = _FakePostgresTenantReadFactory()
    store = object.__new__(PostgresEvidenceStore)
    store._session_factory = factory
    assert store.get(tenant_id="tenant-a", evidence_id="evidence-1") is None
    sql, params = factory.session.calls[0]
    assert "tenant_id = %s AND evidence_id = %s" in sql
    assert params == ("tenant-a", "evidence-1")


def test_evidence_contract_rejects_invalid_confidence_and_unknown_lineage_stage() -> None:
    with pytest.raises(ValueError, match="confidence"):
        EvidenceRecord(tenant_id="t", scope="s", run_id="r", action_type="a", verification_status="ok", confidence=1.1).normalized()
    with pytest.raises(ValueError, match="unsupported evidence lineage stages"):
        EvidenceRecord(tenant_id="t", scope="s", run_id="r", action_type="a", verification_status="ok", lineage={"mystery": "ref"}).normalized()


def test_v1_evidence_database_upgrades_without_losing_legacy_records(tmp_path) -> None:
    db_path = tmp_path / "legacy-evidence.db"
    factory = SqliteSessionFactory(db_path)
    migrations = default_storage_migration_registry()
    v1 = migrations.pending(0)[0]
    with factory.open() as session:
        MigrationRegistry((v1,)).apply_pending(session)
        session.execute(
            """
            INSERT INTO storage_evidence_log(
                evidence_id, tenant_id, partition_key, scope, run_id, action_id, action_type,
                verification_status, created_at, refs_json, payload_json, payload_sha256,
                labels_json, retention_until, legal_hold
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-1", "tenant-a", "evidence_decision:tenant-a", "decision", "run-old", None, "trace",
                "recorded", "2026-01-01T00:00:00+00:00", "[]", "{\"score\":1}", sha256(b'{"score":1}').hexdigest(),
                "{}", None, 0,
            ),
        )
        session.commit()

    upgraded = SqliteEvidenceStore(factory)
    restored = upgraded.get(tenant_id="tenant-a", evidence_id="legacy-1")
    assert restored is not None
    assert restored.schema_version == 2
    assert restored.source == "legacy"
    assert restored.source_type == "legacy"
    assert restored.business_id == "unknown"
    assert restored.observed_at is None
    assert restored.retention_policy == "legacy"
    assert restored.payload == {"score": 1}



class _FakePostgresEvidenceSession:
    dialect = "postgres"

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def fetchone(self, sql, params=None):
        self.calls.append(("fetchone", sql, params))
        return {"deleted_count": 3}

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, params))
        return None


class _FakePostgresEvidenceFactory:
    def __init__(self):
        self.session = _FakePostgresEvidenceSession()

    def open(self):
        return self.session


def test_postgres_retention_counts_before_delete_without_cursor_rowcount() -> None:
    factory = _FakePostgresEvidenceFactory()
    store = object.__new__(PostgresEvidenceStore)
    store._session_factory = factory
    deleted = store.delete_expired(now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    assert deleted == 3
    assert len(factory.session.calls) == 2
    count_call, delete_call = factory.session.calls
    assert count_call[0] == "fetchone"
    assert "COUNT(*) AS deleted_count" in count_call[1]
    assert "legal_hold = 0" in count_call[1]
    assert delete_call[0] == "execute"
    assert delete_call[1].startswith("DELETE FROM storage_evidence_log")
    assert delete_call[2] == count_call[2]
    assert isinstance(delete_call[2][0], str)
    assert delete_call[2][0].endswith("+00:00")

def test_current_schema_missing_canonical_hash_fails_closed(tmp_path) -> None:
    db_path = tmp_path / "missing-hash.db"
    factory = SqliteSessionFactory(db_path)
    store = SqliteEvidenceStore(factory)
    record = store.append(EvidenceRecord(
        tenant_id="tenant-a", scope="provider", run_id="run-1", action_type="sync",
        verification_status="verified", payload={"value": 1}, source="shopify", source_type="provider_api",
        business_id="business-a", observed_at=datetime.now(UTC), retention_policy="evidence_30d",
    ))
    with factory.open() as session:
        session.execute(
            "UPDATE storage_evidence_log SET evidence_sha256 = '' WHERE evidence_id = ?",
            (record.evidence_id,),
        )
    with pytest.raises(ValueError, match="missing canonical hash"):
        store.get(tenant_id="tenant-a", evidence_id=record.evidence_id)


def test_runtime_read_rejects_schema_downgrade_after_controlled_backfill(tmp_path) -> None:
    db_path = tmp_path / "downgrade.db"
    factory = SqliteSessionFactory(db_path)
    store = SqliteEvidenceStore(factory)
    record = store.append(EvidenceRecord(
        tenant_id="tenant-a", scope="provider", run_id="run-1", action_type="sync",
        verification_status="verified", payload={"value": 1}, source="shopify", source_type="provider_api",
        business_id="business-a", observed_at=datetime.now(UTC), retention_policy="evidence_30d",
    ))
    with factory.open() as session:
        session.execute(
            "UPDATE storage_evidence_log SET evidence_schema_version = 1, evidence_sha256 = '' WHERE evidence_id = ?",
            (record.evidence_id,),
        )
    with pytest.raises(ValueError, match="legacy evidence schema requires controlled migration"):
        store.get(tenant_id="tenant-a", evidence_id=record.evidence_id)


def test_persisted_hashes_fail_closed_on_tampering(tmp_path) -> None:
    db_path = tmp_path / "tamper-evidence.db"
    factory = SqliteSessionFactory(db_path)
    store = SqliteEvidenceStore(factory)
    record = store.append(EvidenceRecord(
        tenant_id="tenant-a", scope="provider", run_id="run-1", action_type="sync",
        verification_status="verified", payload={"value": 1}, source="shopify", source_type="provider_api",
        business_id="business-a", observed_at=datetime.now(UTC), retention_policy="evidence_30d",
        lineage={"source": "shopify:1", "action": "sync:1", "outcome": "ok:1"},
    ))
    with factory.open() as session:
        session.execute(
            "UPDATE storage_evidence_log SET payload_json = ? WHERE evidence_id = ?",
            ('{\"value\":2}', record.evidence_id),
        )
        session.commit()
    with pytest.raises(ValueError, match="payload hash mismatch"):
        store.get(tenant_id="tenant-a", evidence_id=record.evidence_id)

    db_path_2 = tmp_path / "tamper-envelope.db"
    factory_2 = SqliteSessionFactory(db_path_2)
    store_2 = SqliteEvidenceStore(factory_2)
    record_2 = store_2.append(EvidenceRecord(
        tenant_id="tenant-a", scope="provider", run_id="run-1", action_type="sync",
        verification_status="verified", payload={"value": 1}, source="shopify", source_type="provider_api",
        business_id="business-a", observed_at=datetime.now(UTC), retention_policy="evidence_30d",
        lineage={"source": "shopify:1", "action": "sync:1", "outcome": "ok:1"},
    ))
    with factory_2.open() as session:
        session.execute(
            "UPDATE storage_evidence_log SET source = ? WHERE evidence_id = ?",
            ("forged-provider", record_2.evidence_id),
        )
        session.commit()
    with pytest.raises(ValueError, match="canonical hash mismatch"):
        store_2.get(tenant_id="tenant-a", evidence_id=record_2.evidence_id)



def test_runtime_append_rejects_legacy_schema_before_persistence(tmp_path) -> None:
    record = EvidenceRecord(
        evidence_id="legacy-runtime-write",
        tenant_id="tenant-a",
        scope="provider",
        run_id="run-legacy",
        action_type="sync",
        verification_status="verified",
        payload={"value": 1},
        source="legacy",
        source_type="legacy",
        business_id="business-a",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        schema_version=1,
    )

    memory = InMemoryEvidenceStore()
    with pytest.raises(ValueError, match="legacy evidence schema requires controlled migration"):
        memory.append(record)
    assert memory.list_for_tenant(tenant_id="tenant-a") == ()

    sqlite = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "reject-runtime-downgrade.db"))
    with pytest.raises(ValueError, match="legacy evidence schema requires controlled migration"):
        sqlite.append(record)
    assert sqlite.get(tenant_id="tenant-a", evidence_id=record.evidence_id) is None

    port = _DistributedEvidencePort([])
    with pytest.raises(ValueError, match="legacy evidence schema requires controlled migration"):
        DistributedEvidenceStore(port).append(record)
    assert port.rows == []


def test_sqlite_retention_compares_offset_time_in_utc(tmp_path) -> None:
    store = SqliteEvidenceStore(SqliteSessionFactory(tmp_path / "retention-offset.db"))
    record = store.append(EvidenceRecord(
        evidence_id="retention-offset",
        tenant_id="tenant-a",
        scope="provider",
        run_id="run-retention",
        action_type="sync",
        verification_status="verified",
        payload={"value": 1},
        source="provider",
        source_type="provider_api",
        business_id="business-a",
        created_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
        retention_until=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    ))

    plus_three = timezone(timedelta(hours=3))
    assert store.delete_expired(now=datetime(2026, 1, 1, 12, 0, tzinfo=plus_three)) == 0
    assert store.get(tenant_id="tenant-a", evidence_id=record.evidence_id) is not None
    assert store.delete_expired(now=datetime(2026, 1, 1, 14, 0, tzinfo=plus_three)) == 1
    assert store.get(tenant_id="tenant-a", evidence_id=record.evidence_id) is None
