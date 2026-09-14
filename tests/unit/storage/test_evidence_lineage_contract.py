from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from storage.evidence_store import EVIDENCE_LINEAGE_STAGES, EvidenceRecord, SqliteEvidenceStore
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
    restored = store.get(record.evidence_id)
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
    restored = upgraded.get("legacy-1")
    assert restored is not None
    assert restored.source == "legacy"
    assert restored.source_type == "legacy"
    assert restored.business_id == "global"
    assert restored.observed_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert restored.retention_policy == "legacy"
    assert restored.payload == {"score": 1}


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
        store.get(record.evidence_id)

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
        store_2.get(record_2.evidence_id)
