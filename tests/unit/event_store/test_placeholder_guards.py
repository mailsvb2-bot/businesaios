from __future__ import annotations

import pytest

from core.events.log import EventLog
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.event_store.postgres_event_store import PostgresEventStore, describe_declared_absence
from runtime.platform.event_store.postgres_event_store_part1 import describe_declared_absence as describe_part1
from runtime.platform.event_store.postgres_event_store_part1 import raise_if_used


def test_postgres_placeholder_describes_itself() -> None:
    meta = describe_declared_absence()
    assert meta["placeholder"] is True
    assert "canonical_module" in meta


def test_postgres_placeholder_runtime_use_fails_closed() -> None:
    store = PostgresEventStore("postgresql://demo")
    with pytest.raises(RuntimeError):
        store.__enter__()


def test_split_placeholder_fails_closed() -> None:
    assert describe_part1()["placeholder"] is True
    with pytest.raises(RuntimeError):
        raise_if_used()




def test_event_log_emit_legacy_marks_payload_in_nonprod(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("PRODUCTION_STRICT_TENANT", raising=False)

    store = MemoryEventStore()
    log = EventLog(store, tenant="tenant-1")
    event = log.emit_legacy(event_type="x", source="s", user_id="u", payload={"a": 1})

    assert event.event_type == "x"
    written = list(store.iter_events(tenant_id="legacy"))
    assert len(written) == 1
    assert written[0]["payload"]["_legacy_event_path"] is True
    assert written[0]["payload"]["_legacy_origin_tenant"] == "tenant-1"


def test_event_log_emit_legacy_forbidden_in_prod_strict(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PRODUCTION_STRICT_TENANT", "1")

    log = EventLog(MemoryEventStore(), tenant="tenant-1")
    with pytest.raises(RuntimeError, match="LEGACY_EVENT_WRITE_FORBIDDEN_IN_PROD"):
        log.emit_legacy(event_type="x", source="s", user_id="u", payload={})


class _SchemaPort:
    def __init__(self, row=(True, True, True)) -> None:
        self.row, self.commits = row, 0

    def fetchone(self, sql, _params=None):
        assert "CREATE " not in sql and "ALTER " not in sql
        return self.row

    def commit(self) -> None:
        self.commits += 1


def test_postgres_event_store_runtime_only_verifies_migrated_schema() -> None:
    store, port = PostgresEventStore("postgresql://demo", enabled=True), _SchemaPort()
    store._port = port
    store._verify_schema()
    assert port.commits == 1


def test_postgres_event_store_runtime_fails_closed_without_v2_migration() -> None:
    store, port = PostgresEventStore("postgresql://demo", enabled=True), _SchemaPort((False, True, True))
    store._port = port
    with pytest.raises(RuntimeError, match="POSTGRES_EVENT_STORE_SCHEMA_MIGRATION_REQUIRED"):
        store._verify_schema()
