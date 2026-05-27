from __future__ import annotations

import json

from core.ai.decision import Decision
from core.security.keyring import Keyring
from kernel.decision_crypto import signed_envelope_from_decision
from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive
from observability.platform.snapshot_store.sqlite_snapshot_store import SqliteSnapshotStore


def _make_env():
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    decision = Decision(
        decision_id="dec-1",
        issuer_id="businesaios-core",
        issued_at_ms=100,
        expires_at_ms=200,
        policy_id="p1",
        action="send_message@v1",
        payload={"x": 1},
        snapshot_id="snap-1",
        state_hash="h1",
        correlation_id="c1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    return signed_envelope_from_decision(decision=decision, keyring=keyring)


def test_sqlite_snapshot_store_round_trip_and_metadata(tmp_path):
    db_path = tmp_path / "snapshots.db"
    with SqliteSnapshotStore(str(db_path), tenant_id="Tenant-A") as store:
        store.put("snap-1", b"abc")
        assert store.get("snap-1") == b"abc"
        row = store._db.fetchone(
            "SELECT tenant_id, partition_key, content_sha256, size_bytes FROM snapshots WHERE snapshot_id = ?",
            ("snap-1",),
        )
        assert row is not None
        assert row[0] == "Tenant-A"
        assert row[1] == "snapshot_store:Tenant-A"
        assert row[3] == 3


def test_sqlite_decision_archive_round_trip_and_metadata(tmp_path):
    db_path = tmp_path / "archive.db"
    env = _make_env()
    with SqliteDecisionArchive(str(db_path), tenant_id="Tenant-A") as archive:
        archive.put(env)
        restored = archive.get("dec-1")
        assert restored is not None
        assert restored.decision.decision_id == env.decision.decision_id
        assert restored.kid == env.kid
        row = archive._db.fetchone(
            "SELECT tenant_id, partition_key, payload_sha256, signature_kid, envelope_json FROM decision_archive WHERE decision_id = ?",
            ("dec-1",),
        )
        assert row is not None
        assert row[0] == "Tenant-A"
        assert row[1] == "decision_archive:Tenant-A"
        assert row[3] == env.kid
        payload = json.loads(row[4])
        assert payload["decision"]["decision_id"] == "dec-1"
