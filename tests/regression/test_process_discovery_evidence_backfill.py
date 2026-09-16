from __future__ import annotations

from datetime import UTC, datetime

from application.process_discovery.canonical_adapters import (
    PROCESS_OBSERVATION_EVENT,
    CanonicalProcessEvidenceStore,
)
from observability.platform.telemetry.event_store import SqliteEventStore
from storage.evidence_store import SqliteEvidenceStore
from storage.sqlite_fallback import SqliteSessionFactory


def _legacy_observation_payload() -> dict:
    return {
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "process_key": "invoice_follow_up",
        "occurred_at": datetime(2026, 9, 1, 8, 30, tzinfo=UTC).isoformat(),
        "source": "owner_asserted",
        "evidence_id": "pev_legacy_restart_001",
        "manual_minutes": 35,
        "actor_cost_per_hour_minor": 60_000,
        "direct_loss_minor": None,
        "revenue_at_risk_minor": 12_000,
        "currency": "RUB",
        "automation_fit": 0.8,
        "operational_risk": 0.25,
        "trust_weight": 0.65,
        "metadata": {
            "assertion_kind": "owner_process_occurrence",
            "server_issued_evidence_id": True,
        },
    }


def test_persisted_legacy_process_observation_backfills_canonical_evidence_after_restart(tmp_path) -> None:
    telemetry_path = tmp_path / "telemetry.sqlite3"
    evidence_path = tmp_path / "evidence.sqlite3"

    telemetry = SqliteEventStore(telemetry_path)
    telemetry.append(
        tenant_id="tenant-a",
        user_id="owner-a",
        event_type=PROCESS_OBSERVATION_EVENT,
        payload=_legacy_observation_payload(),
    )
    telemetry.close()

    telemetry = SqliteEventStore(telemetry_path)
    canonical = SqliteEvidenceStore(SqliteSessionFactory(evidence_path))
    adapter = CanonicalProcessEvidenceStore(telemetry, canonical)

    loaded = adapter.load_process_observations(tenant_id="tenant-a", business_id="business-a")
    assert len(loaded) == 1
    record = canonical.get(tenant_id="tenant-a", evidence_id="pev_legacy_restart_001")
    assert record is not None
    assert record.business_id == "business-a"
    assert record.source_type == "owner_process_observation"
    assert record.observed_at == datetime(2026, 9, 1, 8, 30, tzinfo=UTC)
    assert record.payload["process_key"] == "invoice_follow_up"
    telemetry.close()

    telemetry = SqliteEventStore(telemetry_path)
    canonical = SqliteEvidenceStore(SqliteSessionFactory(evidence_path))
    adapter = CanonicalProcessEvidenceStore(telemetry, canonical)

    replayed = adapter.load_process_observations(tenant_id="tenant-a", business_id="business-a")
    assert replayed == loaded
    records = canonical.list_for_tenant(tenant_id="tenant-a")
    assert len(records) == 1
    assert records[0].evidence_id == "pev_legacy_restart_001"
    telemetry.close()
