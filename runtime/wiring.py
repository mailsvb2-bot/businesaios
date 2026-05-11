from __future__ import annotations

"""Canonical storage-wiring owner for runtime boot.

This root surface is allowed to build storage adapters, but it must not become
an alternative runtime assembly path, registry surface, or decision owner.
"""

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from runtime.platform.config.env_flags import env_bool, env_path, env_str

CANON_RUNTIME_WIRING_OWNER = True
CANON_RUNTIME_WIRING_STORAGE_ONLY = True
CANON_RUNTIME_WIRING_NO_DECISION_LOGIC = True
CANON_RUNTIME_WIRING_NO_ROOT_REGISTRY = True


@dataclass(frozen=True)
class StorageConfig:
    env: str
    backend: str  # sqlite | postgres
    postgres_dsn: str | None
    postgres_event_store_enabled: bool = False


def _sqlite_path(env_name: str, *, base_dir: str, filename: str) -> str:
    return str(env_path(env_name, str(Path(base_dir) / filename)))


def resolve_storage_config() -> StorageConfig:
    env = (env_str("APP_ENV") or env_str("ENV", "dev")).strip().lower() or "dev"
    pg_dsn = (env_str("POSTGRES_DSN").strip() or env_str("DATABASE_URL").strip() or None)
    engine = (env_str("METRO_DB_ENGINE").strip().lower() or "")
    backend_default = "postgres" if (pg_dsn or engine == "postgres") else "sqlite"
    backend = (env_str("STORAGE_BACKEND", backend_default) or backend_default).strip().lower()
    postgres_event_store_enabled = env_bool("BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE", False)

    if env == "prod":
        if backend != "postgres":
            raise RuntimeError(f"PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:{backend}")
        if not pg_dsn:
            raise RuntimeError("PROD_REQUIRES_POSTGRES_DSN")
        if not postgres_event_store_enabled:
            raise RuntimeError("PROD_REQUIRES_EXPLICIT_POSTGRES_EVENT_STORE_ENABLEMENT")

    return StorageConfig(
        env=env,
        backend=backend,
        postgres_dsn=pg_dsn,
        postgres_event_store_enabled=postgres_event_store_enabled,
    )


def build_durable_stores(stack: ExitStack, *, base_dir: str, storage: StorageConfig):
    """Return (event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox)."""

    if storage.backend == "postgres":
        assert storage.postgres_dsn
        from observability.platform.decision_archive.postgres_decision_archive import PostgresDecisionArchive
        from runtime.platform.event_store.postgres_event_store import PostgresEventStore
        from runtime.platform.ledger.postgres_ledger import PostgresLedger
        from runtime.platform.outbox.postgres_outbox import PostgresOutbox
        from runtime.platform.outbox.postgres_payment_outbox import PostgresPaymentOutbox
        from observability.platform.snapshot_store.postgres_snapshot_store import PostgresSnapshotStore

        event_store = stack.enter_context(PostgresEventStore(storage.postgres_dsn, enabled=storage.postgres_event_store_enabled))
        ledger = stack.enter_context(PostgresLedger(storage.postgres_dsn))
        snapshot_store = stack.enter_context(PostgresSnapshotStore(storage.postgres_dsn))
        decision_archive = stack.enter_context(PostgresDecisionArchive(storage.postgres_dsn))
        outbox = stack.enter_context(PostgresOutbox(storage.postgres_dsn))
        payment_outbox = stack.enter_context(PostgresPaymentOutbox(storage.postgres_dsn))
        return event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox

    from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
    from runtime.platform.ledger.sqlite_ledger import SqliteLedger
    from runtime.platform.outbox.sqlite_outbox import SqliteOutbox
    from runtime.platform.outbox.sqlite_payment_outbox import SqlitePaymentOutbox
    from observability.platform.snapshot_store.sqlite_snapshot_store import SqliteSnapshotStore

    event_store = stack.enter_context(SqliteEventStore(_sqlite_path("EVENTS_SQLITE_PATH", base_dir=base_dir, filename="events.db")))
    ledger = stack.enter_context(SqliteLedger(_sqlite_path("LEDGER_SQLITE_PATH", base_dir=base_dir, filename="ledger.db")))
    snapshot_store = stack.enter_context(SqliteSnapshotStore(_sqlite_path("SNAPSHOT_SQLITE_PATH", base_dir=base_dir, filename="snapshots.db")))
    decision_archive = stack.enter_context(SqliteDecisionArchive(_sqlite_path("DECISIONS_SQLITE_PATH", base_dir=base_dir, filename="decisions.db")))
    outbox = stack.enter_context(SqliteOutbox(_sqlite_path("OUTBOX_SQLITE_PATH", base_dir=base_dir, filename="outbox.db")))
    payment_outbox = stack.enter_context(SqlitePaymentOutbox(_sqlite_path("PAYMENT_OUTBOX_SQLITE_PATH", base_dir=base_dir, filename="payment_outbox.db")))
    return event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox


def build_behavior_graph_store(stack: ExitStack, *, base_dir: str, storage: StorageConfig):
    """Return BehaviorGraphStore adapter (sqlite/postgres).

    This is kept separate from build_durable_stores() to avoid tuple churn.
    """
    if storage.backend == "postgres":
        assert storage.postgres_dsn
        from runtime.platform.behavior_graph.postgres_behavior_graph_store import PostgresBehaviorGraphStore

        return stack.enter_context(PostgresBehaviorGraphStore(storage.postgres_dsn))

    from runtime.platform.behavior_graph.sqlite_behavior_graph_store import SqliteBehaviorGraphStore

    return stack.enter_context(
        SqliteBehaviorGraphStore(_sqlite_path("BEHAVIOR_GRAPH_SQLITE_PATH", base_dir=base_dir, filename="behavior_graph.db"))
    )


__all__ = [
    "CANON_RUNTIME_WIRING_NO_DECISION_LOGIC",
    "CANON_RUNTIME_WIRING_NO_ROOT_REGISTRY",
    "CANON_RUNTIME_WIRING_OWNER",
    "CANON_RUNTIME_WIRING_STORAGE_ONLY",
    "StorageConfig",
    "build_behavior_graph_store",
    "build_durable_stores",
    "resolve_storage_config",
]
