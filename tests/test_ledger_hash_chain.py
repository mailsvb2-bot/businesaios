from __future__ import annotations

import tempfile
from pathlib import Path

from core.ai.decision import Decision, DecisionEnvelope
from core.utils.canonical import payload_hash
from core.utils.hash_chain import GENESIS, entry_hash
from runtime.inmemory_ledger import InMemoryLedger
from runtime.platform.ledger.sqlite_ledger import SqliteLedger


def _mk_env(decision_id: str, *, action: str = "send_message@v1") -> DecisionEnvelope:
    d = Decision(
        decision_id=decision_id,
        issuer_id="issuer",
        issued_at_ms=1,
        expires_at_ms=2,
        policy_id="p",
        action=action,
        payload={"x": 1},
        snapshot_id="s",
        state_hash="h",
        correlation_id=decision_id,
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    ph = payload_hash(d.payload)
    return DecisionEnvelope(decision=d, payload_hash=ph, signature="sig", kid="k1", envelope_version=1)


def test_inmemory_ledger_hash_chain_verifies_and_detects_tamper():
    led = InMemoryLedger()
    # Populate WITHOUT calling try_mark_executed (forbidden outside RuntimeGuard).
    env1 = _mk_env("d1")
    env2 = _mk_env("d2")
    prev = GENESIS
    for env in (env1, env2):
        d = env.decision
        fields = {
            "decision_id": d.decision_id,
            "action": d.action,
            "payload_hash": env.payload_hash,
            "signature": env.signature,
            "kid": env.kid,
        }
        h = entry_hash(prev_hash=prev, fields=fields)
        led._done.add(d.decision_id)  # type: ignore[attr-defined]
        led._chain.append((d.decision_id, fields, h))  # type: ignore[attr-defined]
        led._chain_last = h  # type: ignore[attr-defined]
        prev = h
    assert led.verify_chain() is True

    # Tamper with stored hash.
    led._chain[0] = (led._chain[0][0], led._chain[0][1], "0" * 64)  # type: ignore[attr-defined]
    assert led.verify_chain() is False


def test_sqlite_ledger_verify_chain_recomputes_content():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "ledger.db")
        with SqliteLedger(db) as led:
            # Populate tables WITHOUT calling try_mark_executed (forbidden outside RuntimeGuard).
            assert led._db is not None  # noqa: SLF001 (test)
            cur = led._db.cursor()

            env1 = _mk_env("d1")
            env2 = _mk_env("d2")
            for env in (env1, env2):
                d = env.decision
                cur.execute(
                    "INSERT INTO executed (decision_id, executed_at_ms, policy_id, action, payload_hash, signature, snapshot_id, state_hash, kid, correlation_id, envelope_version, state_schema_version, action_schema_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    (
                        d.decision_id,
                        1,
                        d.policy_id,
                        d.action,
                        env.payload_hash,
                        env.signature,
                        d.snapshot_id,
                        d.state_hash,
                        env.kid,
                        d.correlation_id,
                        env.envelope_version,
                        d.state_schema_version,
                        d.action_schema_version,
                    ),
                )

            prev = GENESIS
            for env in (env1, env2):
                d = env.decision
                fields = {
                    "decision_id": d.decision_id,
                    "action": d.action,
                    "payload_hash": env.payload_hash,
                    "signature": env.signature,
                    "kid": env.kid,
                }
                h = entry_hash(prev_hash=prev, fields=fields)
                cur.execute(
                    "INSERT INTO executed_chain (decision_id, prev_hash, entry_hash) VALUES (?, ?, ?);",
                    (d.decision_id, prev, h),
                )
                prev = h

            led._db.commit()
            assert led.verify_chain() is True

            # Tamper: rewrite first entry_hash and adjust second prev_hash so linkage alone would pass.
            cur.execute("UPDATE executed_chain SET entry_hash=? WHERE seq=1;", ("B" * 64,))
            cur.execute("UPDATE executed_chain SET prev_hash=? WHERE seq=2;", ("B" * 64,))
            led._db.commit()

            # Must fail because verify_chain recomputes entry_hash from executed fields.
            assert led.verify_chain() is False
