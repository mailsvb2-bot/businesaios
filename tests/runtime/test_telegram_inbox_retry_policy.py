import json
import sqlite3

from runtime.platform.telegram_inbox import TelegramInbox


def test_retry_limit_dead_letters_without_deleting_and_allows_explicit_requeue(
    monkeypatch, tmp_path,
):
    db_path = tmp_path / "delivery_state.db"
    monkeypatch.setenv("DELIVERY_STATE_DB_PATH", str(db_path))
    inbox = TelegramInbox("test-token")
    update = {
        "update_id": 42,
        "callback_query": {
            "id": "callback-42",
            "data": "cp:section:sales",
        },
    }

    assert inbox.stage([update]) == 43
    assert inbox.backlog_counts() == {"pending": 1, "dead_letter": 0}
    assert inbox.failed(42, ValueError("schema"), max_attempts=2) == "pending"
    assert inbox.failed(42, ValueError("schema"), max_attempts=2) == "dead_letter"
    assert inbox.backlog_counts() == {"pending": 0, "dead_letter": 1}
    assert inbox.due() == []

    with sqlite3.connect(str(db_path)) as db:
        row = db.execute(
            "SELECT status,payload FROM telegram_ingress_inbox WHERE bot_scope=? AND update_id=?",
            (inbox.scope, 42),
        ).fetchone()
    assert row is not None
    assert row[0] == "dead_letter"
    assert json.loads(row[1]) == update

    assert inbox.requeue_dead_letter(42) is True
    assert inbox.requeue_dead_letter(42) is False
    assert inbox.backlog_counts() == {"pending": 1, "dead_letter": 0}
    assert inbox.due() == [update]
    inbox.complete(42)
    with sqlite3.connect(str(db_path)) as db:
        row = db.execute(
            "SELECT status,payload FROM telegram_ingress_inbox WHERE bot_scope=? AND update_id=?",
            (inbox.scope, 42),
        ).fetchone()
    assert row is not None
    assert row[0] == "completed"
    assert json.loads(row[1]) == update
