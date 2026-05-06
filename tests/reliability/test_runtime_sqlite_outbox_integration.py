from __future__ import annotations

import time

from runtime.platform.outbox.sqlite_outbox import SqliteOutbox


def test_sqlite_outbox_reclaims_stale_delivering_message(tmp_path):
    ctx = SqliteOutbox(str(tmp_path / "outbox.db"))
    outbox = ctx.__enter__()
    try:
        assert outbox.enqueue_once(
            decision_id="d1",
            correlation_id="c1",
            action="send_message@v1",
            payload_json="{}",
        )
        assert outbox.claim("d1")
        # force stale claim
        outbox._conn.execute("UPDATE outbox SET claimed_at_ms=? WHERE decision_id=?", (int(time.time() * 1000) - outbox._lease_ms - 1, "d1"))
        outbox._conn.commit()
        items = outbox.list_claimable(limit=10)
        assert items and items[0]["decision_id"] == "d1"
        assert outbox.claim("d1")
        assert outbox.status("d1") == "delivering"
    finally:
        ctx.__exit__(None, None, None)
