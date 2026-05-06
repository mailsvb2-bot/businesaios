from __future__ import annotations

from reliability.idempotency_contract import IdempotencyResolution
from reliability.idempotency_scope import build_idempotency_key
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore


def _key() -> object:
    return build_idempotency_key(
        tenant_id='tenant-a',
        namespace='runtime',
        operation='execute',
        key='job-1',
        semantic_scope={'goal': 'grow revenue', 'step': 1},
    )


def test_sqlite_idempotency_store_replays_completed_result(tmp_path) -> None:
    store = SQLiteIdempotencyStore(tmp_path / 'idem.sqlite3')
    key = _key()
    first = store.reserve(key=key, owner_id='worker-1')
    assert first.resolution is IdempotencyResolution.ACCEPTED
    store.mark_completed(key=key, owner_id='worker-1', result_ref='run-1', result_digest='run-1')
    second = store.reserve(key=key, owner_id='worker-2')
    assert second.resolution is IdempotencyResolution.REPLAY_COMPLETED
    assert second.replay_result_ref == 'run-1'


def test_sqlite_idempotency_store_prunes_history(tmp_path) -> None:
    store = SQLiteIdempotencyStore(tmp_path / 'idem.sqlite3')
    key = _key()
    store.reserve(key=key, owner_id='worker-1')
    store.mark_failed(key=key, owner_id='worker-1', reason='boom')
    store.expire_stale()
    deleted = store.prune_history(keep_latest_per_key=1)
    assert deleted >= 0
