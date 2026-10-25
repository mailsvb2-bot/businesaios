"""Execute-once contract for every decision ledger: a decision_id is claimed exactly once."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.inmemory_ledger import InMemoryLedger
from runtime.platform.ledger.sqlite_ledger import SqliteLedger


def _env(decision_id: str, action: str = "send_message@v1", payload: dict | None = None):
    return SimpleNamespace(decision=SimpleNamespace(decision_id=decision_id, action=action, payload=payload or {}))


@pytest.fixture(params=["memory", "sqlite"])
def ledger(request, tmp_path):
    if request.param == "memory":
        yield InMemoryLedger()
        return
    with SqliteLedger(str(tmp_path / "ledger.sqlite")) as db:
        yield db


def test_second_claim_of_same_decision_id_is_refused(ledger) -> None:
    assert ledger.try_mark_executed(_env("d-1")) is True
    assert ledger.try_mark_executed(_env("d-1")) is False
    assert ledger.is_executed("d-1") is True


def test_replay_with_different_payload_is_still_refused(ledger) -> None:
    assert ledger.try_mark_executed(_env("d-2", payload={"a": 1})) is True
    assert ledger.try_mark_executed(_env("d-2", action="other@v1", payload={"a": 2})) is False


def test_distinct_decision_ids_do_not_block_each_other(ledger) -> None:
    assert ledger.try_mark_executed(_env("d-3")) is True
    assert ledger.try_mark_executed(_env("d-4")) is True
    assert ledger.is_executed("d-3") and ledger.is_executed("d-4")
    assert not ledger.is_executed("d-never")


def test_empty_decision_id_is_never_claimed(ledger) -> None:
    assert ledger.try_mark_executed(_env("")) is False
    assert ledger.try_mark_executed(_env("")) is False


def test_sqlite_ledger_claim_survives_reopen(tmp_path) -> None:
    path = str(tmp_path / "persist.sqlite")
    with SqliteLedger(path) as first:
        assert first.try_mark_executed(_env("d-5")) is True
    with SqliteLedger(path) as second:
        assert second.is_executed("d-5") is True
        assert second.try_mark_executed(_env("d-5")) is False


def test_memory_ledger_chain_stays_valid_and_ignores_refused_replays() -> None:
    ledger = InMemoryLedger()
    ledger.try_mark_executed(_env("d-6"))
    ledger.try_mark_executed(_env("d-6"))
    ledger.try_mark_executed(_env("d-7"))
    assert ledger.verify_chain() is True
    assert len(ledger._chain) == 2
