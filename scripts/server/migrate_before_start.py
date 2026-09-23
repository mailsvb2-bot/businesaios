from __future__ import annotations

from contextlib import ExitStack

from runtime.wiring import build_behavior_graph_store, build_durable_stores, resolve_storage_config

CANON_MIGRATION_BEFORE_START = True


def main() -> int:
    storage = resolve_storage_config()
    with ExitStack() as stack:
        event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox = build_durable_stores(
            stack,
            base_dir='runtime/data',
            storage=storage,
        )
        behavior_graph_store = build_behavior_graph_store(
            stack,
            base_dir='runtime/data',
            storage=storage,
        )
        for target in (
            event_store,
            ledger,
            snapshot_store,
            decision_archive,
            outbox,
            payment_outbox,
            behavior_graph_store,
        ):
            ping = getattr(target, 'ping', None)
            if callable(ping):
                ping()
    print(f'MIGRATIONS_READY backend={storage.backend}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
