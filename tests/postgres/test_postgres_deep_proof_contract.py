from __future__ import annotations

from runtime.platform.postgres_contract import PostgresRuntimeProof, evaluate_postgres_contract
from runtime.platform.postgres_live_probe import PostgresLiveProbeConfig


_READY_PROOF = dict(
    database_url_present=True,
    postgres_enabled=True,
    psycopg_available=True,
    live_probe_ok=True,
    schema_objects_present=(
        "events",
        "runtime_outbox",
        "payment_outbox",
        "decision_archive",
        "evidence_archive",
        "runtime_snapshots",
        "execution_ledger",
        "recovery_queue",
    ),
    migrations_applied=(
        "events_v1",
        "runtime_outbox_v1",
        "decision_archive_v1",
        "evidence_archive_v1",
        "execution_ledger_v1",
        "recovery_queue_v1",
    ),
    event_store_roundtrip_ok=True,
    outbox_roundtrip_ok=True,
    recovery_contract_ok=True,
    rollback_roundtrip_ok=True,
    backup_evidence_ok=True,
    ledger_chain_verification_ok=True,
)


def test_postgres_contract_requires_rollback_backup_and_ledger_chain() -> None:
    proof = PostgresRuntimeProof(**{**_READY_PROOF, "backup_evidence_ok": False})

    payload = evaluate_postgres_contract(proof)

    assert payload["status"] == "blocked"
    assert "postgres_backup_evidence_required" in payload["violations"]
    assert payload["rollback_roundtrip_ok"] is True
    assert payload["ledger_chain_verification_ok"] is True
    assert payload["claims_production_ready"] is False


def test_postgres_contract_ready_requires_all_deep_proofs() -> None:
    payload = evaluate_postgres_contract(PostgresRuntimeProof(**_READY_PROOF))

    assert payload["status"] == "ready"
    assert payload["violations"] == []
    assert payload["backup_evidence_ok"] is True
    assert payload["rollback_roundtrip_ok"] is True
    assert payload["ledger_chain_verification_ok"] is True
    assert payload["claims_production_ready"] is False


def test_live_probe_config_defaults_backup_evidence_to_fail_closed() -> None:
    config = PostgresLiveProbeConfig(dsn="postgresql://runtime-db")

    assert config.backup_evidence_ok is False
