from __future__ import annotations

import json
import sqlite3

import pytest

from runtime.platform import market_intelligence_state_store as module
from runtime.platform.market_intelligence_state_store import (
    SqliteMarketIntelligenceStateStore,
    SyncCheckpoint,
    _default_state_path,
    _json_mapping,
    _non_negative_int,
    _safe_json,
    _utc_now,
)


def checkpoint(
    *,
    tenant_id: str = "tenant-a",
    provider: str = "provider-a",
    source_family: str = "search",
    scope_key: str = "scope-a",
    cursor: str | None = "cursor-1",
    metadata=None,
) -> SyncCheckpoint:
    return SyncCheckpoint(
        tenant_id=tenant_id,
        provider=provider,
        source_family=source_family,
        scope_key=scope_key,
        cursor=cursor,
        last_seen_at="2026-07-20T00:00:00+00:00",
        checksum="sum",
        schema_version=2,
        metadata={"x": 1} if metadata is None else metadata,
    )


def begin(
    store: SqliteMarketIntelligenceStateStore,
    *,
    run_id="run-1",
    tenant_id="tenant-a",
    operation="scan",
    replay_key="replay-1",
):
    store.begin_run(
        run_id=run_id,
        tenant_id=tenant_id,
        provider="provider-a",
        source_family="search",
        scope_key="scope-a",
        operation=operation,
        replay_key=replay_key,
        checkpoint_before=checkpoint(tenant_id=tenant_id),
        metadata={"attempt": 1},
    )


def test_helpers_and_default_path(monkeypatch, tmp_path):
    assert "+00:00" in _utc_now()
    assert _safe_json({"b": 1, "a": 2}) == '{"a": 2, "b": 1}'
    assert _json_mapping('{"x": 1}', field="field") == {"x": 1}
    with pytest.raises(ValueError, match="field must contain a JSON object"):
        _json_mapping("[]", field="field")
    with pytest.raises(json.JSONDecodeError):
        _json_mapping("not-json", field="field")

    assert _non_negative_int("2", field="count") == 2
    for value in (True, "bad", -1):
        with pytest.raises(ValueError, match="count must be a non-negative integer"):
            _non_negative_int(value, field="count")

    monkeypatch.setattr(module, "runtime_data_dir", lambda: tmp_path)
    assert _default_state_path() == tmp_path / "market_intelligence" / "state.sqlite3"


def test_migration_connect_cleanup_and_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "nested" / "state.sqlite3"
    store = SqliteMarketIntelligenceStateStore(path)
    assert path.exists()
    second = SqliteMarketIntelligenceStateStore(path)
    assert second.db_path == path

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM mi_schema_version").fetchone()[0] == 1

    with pytest.raises(RuntimeError, match="boom"):
        with store._connect() as conn:
            conn.execute("SELECT 1")
            raise RuntimeError("boom")

    missing = store.load_checkpoint(
        tenant_id="tenant-a",
        provider="provider-a",
        source_family="search",
        scope_key="missing",
    )
    assert missing == SyncCheckpoint("tenant-a", "provider-a", "search", "missing", None, None, None, 1, {})

    first = checkpoint()
    assert store.save_checkpoint(first) is first
    assert store.load_checkpoint(
        tenant_id="tenant-a",
        provider="provider-a",
        source_family="search",
        scope_key="scope-a",
    ) == first
    updated = checkpoint(cursor="cursor-2", metadata={})
    store.save_checkpoint(updated)
    assert store.load_checkpoint(
        tenant_id="tenant-a",
        provider="provider-a",
        source_family="search",
        scope_key="scope-a",
    ).cursor == "cursor-2"

    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE mi_checkpoint SET metadata_json='[]'")
        conn.commit()
    with pytest.raises(ValueError, match="checkpoint metadata"):
        store.load_checkpoint(
            tenant_id="tenant-a",
            provider="provider-a",
            source_family="search",
            scope_key="scope-a",
        )


def test_run_lifecycle_replay_and_restart_contracts(tmp_path):
    store = SqliteMarketIntelligenceStateStore(tmp_path / "state.sqlite3")
    begin(store)
    assert len(store.reconcile_incomplete_runs()) == 1
    assert len(store.reconcile_incomplete_runs(tenant_id="tenant-a")) == 1
    assert store.reconcile_incomplete_runs(tenant_id="") == ()
    with pytest.raises(ValueError, match="cannot be restarted from status running"):
        begin(store)

    with pytest.raises(ValueError, match="unsupported terminal run status"):
        store.finish_run(
            run_id="run-1",
            status="future",
            checkpoint_after=checkpoint(),
            records_count=0,
            pages_fetched=0,
        )
    for field, kwargs in (
        ("records_count", {"records_count": -1, "pages_fetched": 0}),
        ("pages_fetched", {"records_count": 0, "pages_fetched": True}),
    ):
        with pytest.raises(ValueError, match=field):
            store.finish_run(
                run_id="run-1",
                status="failed",
                checkpoint_after=checkpoint(),
                **kwargs,
            )

    store.finish_run(
        run_id="run-1",
        status="failed",
        checkpoint_after=checkpoint(),
        records_count=0,
        pages_fetched=1,
        error_code="temporary",
        error_message="retry",
        poisoned=True,
        quarantined=True,
    )
    assert store.reconcile_incomplete_runs() == ()
    begin(store)
    store.finish_run(
        run_id="run-1",
        status="dry_run",
        checkpoint_after=checkpoint(),
        records_count=0,
        pages_fetched=0,
    )
    begin(store)
    store.finish_run(
        run_id="run-1",
        status="succeeded",
        checkpoint_after=checkpoint(),
        records_count=3,
        pages_fetched=2,
    )
    assert store.has_successful_replay(
        tenant_id="tenant-a",
        provider="provider-a",
        source_family="search",
        scope_key="scope-a",
        replay_key="replay-1",
    )
    assert not store.has_successful_replay(
        tenant_id="tenant-a",
        provider="provider-a",
        source_family="search",
        scope_key="scope-a",
        replay_key="other",
    )
    with pytest.raises(ValueError, match="cannot be restarted from status succeeded"):
        begin(store)
    with pytest.raises(ValueError, match="running market-intelligence run not found"):
        store.finish_run(
            run_id="missing",
            status="failed",
            checkpoint_after=checkpoint(),
            records_count=0,
            pages_fetched=0,
        )


def test_run_id_collision_is_rejected_after_terminal_failure(tmp_path):
    store = SqliteMarketIntelligenceStateStore(tmp_path / "state.sqlite3")
    begin(store)
    store.finish_run(
        run_id="run-1",
        status="failed",
        checkpoint_after=checkpoint(),
        records_count=0,
        pages_fetched=0,
    )
    with pytest.raises(ValueError, match="collision across identities"):
        begin(store, operation="different")


def test_quarantine_lifecycle_and_upsert(tmp_path):
    store = SqliteMarketIntelligenceStateStore(tmp_path / "state.sqlite3")
    scope = {
        "tenant_id": "tenant-a",
        "provider": "provider-a",
        "source_family": "search",
        "scope_key": "scope-a",
    }
    assert not store.is_quarantined(**scope)
    store.quarantine_scope(**scope, reason_code="invalid", details=None)
    assert store.is_quarantined(**scope)
    store.quarantine_scope(**scope, reason_code="poisoned", details={"x": 1})
    assert store.is_quarantined(**scope)
    store.release_quarantine(**scope)
    assert not store.is_quarantined(**scope)
    store.release_quarantine(**scope)


def test_dead_letter_is_idempotent_but_rejects_cross_identity_collision(tmp_path):
    store = SqliteMarketIntelligenceStateStore(tmp_path / "state.sqlite3")
    args = {
        "event_id": "event-1",
        "run_id": "run-1",
        "tenant_id": "tenant-a",
        "provider": "provider-a",
        "source_family": "search",
        "scope_key": "scope-a",
        "reason_code": "invalid",
        "payload": {"x": 1},
    }
    store.dead_letter(**args)
    store.dead_letter(**args)
    with pytest.raises(ValueError, match="dead-letter event_id collision"):
        store.dead_letter(**{**args, "tenant_id": "tenant-b"})
