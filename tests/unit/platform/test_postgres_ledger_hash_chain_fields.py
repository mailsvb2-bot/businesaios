from __future__ import annotations

from runtime.platform.ledger.postgres_ledger import PostgresLedger
from runtime.platform.utils.hash_chain import entry_hash


def test_postgres_ledger_chain_fields_include_action_and_kid() -> None:
    fields = PostgresLedger._chain_fields(
        decision_id="decision-1",
        action="send_message@v1",
        payload_hash_value="payload-hash",
        signature="signature",
        kid="kid-1",
    )

    assert fields == {
        "decision_id": "decision-1",
        "action": "send_message@v1",
        "payload_hash": "payload-hash",
        "signature": "signature",
        "kid": "kid-1",
    }


def test_postgres_ledger_chain_hash_changes_when_action_or_kid_changes() -> None:
    base = PostgresLedger._chain_fields(
        decision_id="decision-1",
        action="send_message@v1",
        payload_hash_value="payload-hash",
        signature="signature",
        kid="kid-1",
    )
    changed_action = dict(base, action="capture_payment@v1")
    changed_kid = dict(base, kid="kid-2")

    assert entry_hash(prev_hash="genesis", fields=base) != entry_hash(prev_hash="genesis", fields=changed_action)
    assert entry_hash(prev_hash="genesis", fields=base) != entry_hash(prev_hash="genesis", fields=changed_kid)
