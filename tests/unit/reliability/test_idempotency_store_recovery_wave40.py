from __future__ import annotations

import json
from pathlib import Path

import pytest

import reliability.idempotency_store as module
from reliability.idempotency_contract import IdempotencyResolution
from reliability.idempotency_store import JsonlIdempotencyStore
from tests.unit.reliability.idempotency_wave40_support import NOW, key, record_row

def test_jsonl_legacy_and_transaction_recovery(tmp_path: Path):
    path = tmp_path / "idempotency.jsonl"
    legacy = record_row("legacy")
    tx_id = "committed"
    committed = record_row("committed")
    ignored = record_row("ignored")
    rows = [
        legacy,
        {module._JOURNAL_FIELD: "begin", "tx_id": tx_id, "count": 1},
        {
            module._JOURNAL_FIELD: "record",
            "tx_id": tx_id,
            "payload": committed,
        },
        {module._JOURNAL_FIELD: "commit", "tx_id": tx_id},
        {module._JOURNAL_FIELD: "begin", "tx_id": "partial", "count": 1},
        {
            module._JOURNAL_FIELD: "record",
            "tx_id": "partial",
            "payload": ignored,
        },
    ]
    path.write_text(
        "\n" + "\n".join(json.dumps(row) for row in rows) + "\n{" + "bad",
        encoding="utf-8",
    )
    store = JsonlIdempotencyStore(path)
    assert store.get(key=key("legacy")) is not None
    assert store.get(key=key("committed")) is not None
    assert store.get(key=key("ignored")) is None
    assert path.read_bytes().endswith(b"\n")
    repaired = store.reserve(key=key("after-repair"), owner_id="owner-a", now=NOW)
    assert repaired.resolution is IdempotencyResolution.ACCEPTED
    assert JsonlIdempotencyStore(path).get(key=key("after-repair")) is not None

    path.unlink()
    store._reload_unlocked()
    assert store._records == {}
    store._append_records_unlocked([])


@pytest.mark.parametrize(
    "rows,match",
    [
        (["[]"], "row must be an object"),
        (["{"], "Expecting property name"),
        ([json.dumps({module._JOURNAL_FIELD: "begin"})], "transaction id"),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "begin",
                        "tx_id": "x",
                        "count": 1,
                    }
                ),
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "begin",
                        "tx_id": "x",
                        "count": 1,
                    }
                ),
            ],
            "duplicate",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "begin",
                        "tx_id": "x",
                        "count": 0,
                    }
                )
            ],
            "count must be > 0",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "record",
                        "tx_id": "x",
                        "payload": {},
                    }
                )
            ],
            "orphan.*record",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "begin",
                        "tx_id": "x",
                        "count": 1,
                    }
                ),
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "record",
                        "tx_id": "x",
                        "payload": [],
                    }
                ),
            ],
            "payload must be an object",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "commit",
                        "tx_id": "x",
                    }
                )
            ],
            "orphan.*commit",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "begin",
                        "tx_id": "x",
                        "count": 2,
                    }
                ),
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "record",
                        "tx_id": "x",
                        "payload": record_row(),
                    }
                ),
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "commit",
                        "tx_id": "x",
                    }
                ),
            ],
            "incomplete",
        ),
        (
            [
                json.dumps(
                    {
                        module._JOURNAL_FIELD: "mystery",
                        "tx_id": "x",
                    }
                )
            ],
            "unknown.*marker",
        ),
    ],
)
def test_jsonl_corruption_fails_closed(tmp_path: Path, rows, match):
    path = tmp_path / "bad.jsonl"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises((ValueError, json.JSONDecodeError), match=match):
        JsonlIdempotencyStore(path)


def test_jsonl_repairs_invalid_utf8_tail_and_separates_valid_tail(tmp_path: Path):
    path = tmp_path / "tails.jsonl"
    path.write_bytes((json.dumps(record_row("legacy")) + "\n").encode() + b"\xff")
    store = JsonlIdempotencyStore(path)
    assert path.read_bytes().endswith(b"\n")
    assert store.get(key=key("legacy")) is not None

    path.write_text(json.dumps(record_row("legacy")), encoding="utf-8")
    store = JsonlIdempotencyStore(path)
    store.reserve(key=key("new"), owner_id="owner-a", now=NOW)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["key"] == "legacy"
    assert json.loads(lines[1])[module._JOURNAL_FIELD] == "begin"


