from __future__ import annotations

import threading
from typing import Optional, Any, Dict

from runtime.ledger import GENESIS, entry_hash, payload_hash



class InMemoryLedger:
    """In-memory decision ledger.

    This ledger is used in tests and local runs.

    Law:
      - MUST support atomic execute-once semantics via try_mark_executed(env)
      - MUST support crash-recovery verification via is_executed(decision_id)

    Backwards-compat:
      - already_executed/mark_executed are kept for reference-mode adapters.
    """

    def __init__(self) -> None:
        self._done: set[str] = set()
        # Tamper-evident chain entries.
        # We store the exact fields used for hashing so verify_chain() can
        # recompute hashes deterministically.
        self._chain: list[tuple[str, Dict[str, Any], str]] = []  # (decision_id, fields, entry_hash)
        self._chain_last: str = GENESIS
        self._lock = threading.Lock()

    # -------- Reference-mode API --------
    def already_executed(self, decision_id: str) -> bool:
        with self._lock:
            return decision_id in self._done

    def mark_executed(self, decision_id: str) -> None:
        with self._lock:
            self._done.add(str(decision_id))

    # -------- Production-mode API --------
    def try_mark_executed(self, env) -> bool:
        """Atomically marks decision as executed.

        Returns False if decision_id already executed.
        """
        decision_id = str(getattr(getattr(env, "decision", env), "decision_id", ""))
        if not decision_id:
            return False
        with self._lock:
            if decision_id in self._done:
                return False
            self._done.add(decision_id)
            fields: Dict[str, Any] = {
                "decision_id": decision_id,
                "action": str(getattr(getattr(env, "decision", env), "action", "")),
                "payload_hash": str(
                    getattr(
                        env,
                        "payload_hash",
                        payload_hash(getattr(getattr(env, "decision", env), "payload", {})),
                    )
                ),
                "signature": str(getattr(env, "signature", "")),
                "kid": str(getattr(env, "kid", "")),
            }
            h = entry_hash(prev_hash=self._chain_last, fields=fields)
            self._chain.append((decision_id, fields, h))
            self._chain_last = h
            return True

    def is_executed(self, decision_id: str) -> bool:
        with self._lock:
            return str(decision_id) in self._done

    def verify_chain(self) -> bool:
        """Verify the tamper-evident chain by recomputing entry hashes."""
        with self._lock:
            prev = GENESIS
            for decision_id, fields, h in self._chain:
                # Minimal integrity: decision_id must match fields.
                if str(fields.get("decision_id")) != str(decision_id):
                    return False
                expected = entry_hash(prev_hash=prev, fields=fields)
                if str(h) != str(expected):
                    return False
                prev = str(h)
            return True
