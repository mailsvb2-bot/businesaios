from __future__ import annotations

"""Canonical storage-wiring owner for runtime boot.

This root surface is allowed to build storage adapters, but it must not become
an alternative runtime assembly path, registry surface, or decision owner.
"""

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.platform.config.env_flags import env_path, env_str

CANON_RUNTIME_WIRING_OWNER = True
CANON_RUNTIME_WIRING_STORAGE_ONLY = True
CANON_RUNTIME_WIRING_NO_DECISION_LOGIC = True
CANON_RUNTIME_WIRING_NO_ROOT_REGISTRY = True
CANON_RUNTIME_WIRING_READINESS_SURFACE = True

DURABLE_STORE_ROLES = (
    "event_store",
    "ledger",
    "snapshot_store",
    "decision_archive",
    "outbox",
    "payment_outbox",
)


@dataclass(frozen=True)
class StorageConfig:
    env: str
    backend: str  # sqlite | postgres
    postgres_dsn: str | None


def _sqlite_path(env_name: str, *, base_dir: str, filename: str) -> str:
    return str(env_path(env_name, str(Path(base_dir) / filename)))


def resolve_storage_config() -> StorageConfig:
    env = (env_str("APP_ENV") or env_str("ENV", "dev")).strip().lower() or "dev"
    pg_dsn = (env_str("POSTGRES_DSN").strip() or env_str("DATABASE_URL").strip() or None)
    engine = (env_str("METRO_DB_ENGINE").strip().lower() or "")
    backend_default = "postgres" if (pg_dsn or engine == "postgres") else "sqlite"
    backend = (env_str("STORAGE_BACKEND", backend_default) or backend_default).strip().lower()

    if env == "prod":
        if backend != "postgres":
            raise RuntimeError(f"PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:{backend}")
        if not pg_dsn:
            raise RuntimeError("PROD_REQUIRES_POSTGRES_DSN")

    return StorageConfig(env=env, backend=backend, postgres_dsn=pg_dsn)


def describe_storage_readiness(storage: StorageConfig) -> dict[str, Any]:
    """Return a side-effect-free storage readiness snapshot for admin/control-plane.

    This function intentionally does not open sockets, import drivers, create
    adapters, or make decisions. It exposes the storage contract that boot will
    enforce, so admin surfaces can show production blockers before startup.
    """
    backend = str(storage.backend or "").strip().lower()
    env = str(storage.env or "").strip().lower() or "dev"
    has_postgres_dsn = bool(str(storage.postgres_dsn or "").strip())
    blockers: list[str] = []
    if env == "prod" and backend != "postgres":
        blockers.append(f"PROD_REQUIRES_POSTGRES_STORAGE_BACKEND:{backend}")
    if env == "prod" and not has_postgres_dsn:
        blockers.append("PROD_REQUIRES_POSTGRES_DSN")
    if backend == "postgres" and not has_postgres_dsn:
        blockers.append("POSTGRES_BACKEND_REQUIRES_DSN")

    return {
        "surface": "runtime.storage.wiring",
        "canonical_owner": "runtime.wiring",
        "storage_only": True,
        "decision_logic": False,
        "backend": backend,
        "env": env,
        "postgres_dsn_configured": has_postgres_dsn,
        "roles": list(DURABLE_STORE_ROLES),
        "live_ready": not blockers,
        "blockers": blockers,
    }


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

        event_store = stack.enter_context(PostgresEventStore(storage.postgres_dsn, enabled=True))
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
    "CANON_RUNTIME_WIRING_READINESS_SURFACE",
    "CANON_RUNTIME_WIRING_STORAGE_ONLY",
    "DURABLE_STORE_ROLES",
    "StorageConfig",
    "build_behavior_graph_store",
    "build_durable_stores",
    "describe_storage_readiness",
    "resolve_storage_config",
]
