from __future__ import annotations

import sqlite3
import time

from observability.platform.observability.silent import swallow
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.platform.utils.canonical import payload_hash
from runtime.platform.utils.hash_chain import GENESIS, entry_hash


class SqliteLedger:
    """Dev DecisionLedger (SQLite).

    Exactly-once is enforced by PRIMARY KEY on decision_id.
    Additionally, we append a tamper-evident hash-chain row on first execution.

    NOTE: SQLite is DEV-only. Production should use PostgreSQL.
    """

    def __init__(self, path: str):
        self._path = str(path)
        self._db: sqlite3.Connection | None = None

    def __enter__(self):
        self._db = sqlite3.connect(self._path, timeout=5.0, check_same_thread=False)
        configure_sqlite(self._db, prod=is_prod_env())
        self._db.execute("PRAGMA journal_mode=WAL;")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS executed ("
            "decision_id TEXT PRIMARY KEY, "
            "executed_at_ms INTEGER, "
            "policy_id TEXT, "
            "action TEXT, "
            "payload_hash TEXT, "
            "signature TEXT, "
            "snapshot_id TEXT, "
            "state_hash TEXT, "
            "kid TEXT, "
            "correlation_id TEXT, "
            "envelope_version INTEGER, "
            "state_schema_version INTEGER, "
            "action_schema_version INTEGER)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS executed_chain ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
            "decision_id TEXT UNIQUE NOT NULL, "
            "prev_hash TEXT NOT NULL, "
            "entry_hash TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS effect_status ("
            "envelope_id TEXT PRIMARY KEY, "
            "status TEXT NOT NULL, "
            "updated_at_ms INTEGER NOT NULL)"
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._db:
            self._db.close()

    def try_mark_executed(self, env) -> bool:
        assert self._db is not None
        decision = getattr(env, "decision", env)
        decision_id = str(getattr(decision, "decision_id", ""))
        if not decision_id:
            return False
        try:
            cur = self._db.cursor()
            cur.execute("BEGIN IMMEDIATE;")
            row = cur.execute("SELECT entry_hash FROM executed_chain ORDER BY seq DESC LIMIT 1;").fetchone()
            prev = row[0] if row and row[0] else GENESIS

            cur.execute(
                "INSERT INTO executed (decision_id, executed_at_ms, policy_id, action, payload_hash, signature, snapshot_id, state_hash, kid, correlation_id, envelope_version, state_schema_version, action_schema_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    decision_id,
                    int(time.time() * 1000),
                    str(getattr(decision, "policy_id", "")),
                    str(getattr(decision, "action", "")),
                    str(getattr(env, "payload_hash", payload_hash(getattr(decision, "payload", {})))),
                    str(getattr(env, "signature", "")),
                    str(getattr(decision, "snapshot_id", "")),
                    str(getattr(decision, "state_hash", "")),
                    str(getattr(env, "kid", "")),
                    str(getattr(decision, "correlation_id", "")),
                    int(getattr(env, "envelope_version", 1)),
                    int(getattr(decision, "state_schema_version", 1)),
                    int(getattr(decision, "action_schema_version", 1)),
                ),
            )

            fields = {
                "decision_id": decision_id,
                "action": str(getattr(decision, "action", "")),
                "payload_hash": str(getattr(env, "payload_hash", payload_hash(getattr(decision, "payload", {})))),
                "signature": str(getattr(env, "signature", "")),
                "kid": str(getattr(env, "kid", "")),
            }
            h = entry_hash(prev_hash=str(prev), fields=fields)
            cur.execute(
                "INSERT INTO executed_chain (decision_id, prev_hash, entry_hash) VALUES (?, ?, ?);",
                (decision_id, str(prev), str(h)),
            )

            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            try:
                self._db.rollback()
            except Exception:
                swallow(__name__, 'runtime/platform/ledger/sqlite_ledger.py')
            return False
        except Exception:
            try:
                self._db.rollback()
            except Exception:
                swallow(__name__, 'runtime/platform/ledger/sqlite_ledger.py')
            return False

    def is_executed(self, decision_id: str) -> bool:
        assert self._db is not None
        cur = self._db.cursor()
        row = cur.execute("SELECT 1 FROM executed WHERE decision_id=? LIMIT 1;", (str(decision_id),)).fetchone()
        return row is not None

    # Reference-mode compatibility
    def already_executed(self, decision_id: str) -> bool:
        return self.is_executed(decision_id)

    def mark_executed(self, decision_id: str) -> None:
        # reference-mode no-op; production uses try_mark_executed
        _ = self.is_executed(decision_id)

    def verify_chain(self) -> bool:
        """Verify tamper-evident chain.

        This verifies BOTH:
          1) linkage: prev_hash pointers are consistent
          2) content: entry_hash == hash(prev_hash || canonical(fields))

        Without (2), an attacker could rewrite history and keep pointers consistent.
        """
        assert self._db is not None
        cur = self._db.cursor()
        rows = cur.execute(
            "SELECT c.seq, c.decision_id, c.prev_hash, c.entry_hash FROM executed_chain c ORDER BY c.seq ASC;"
        ).fetchall()
        prev = GENESIS
        for _seq, decision_id, prev_hash, entry_h in rows:
            if str(prev_hash) != str(prev):
                return False

            # Recompute entry hash from executed ledger fields.
            ex = cur.execute(
                "SELECT action, payload_hash, signature, kid FROM executed WHERE decision_id=? LIMIT 1;",
                (str(decision_id),),
            ).fetchone()
            if not ex:
                return False
            action, ph, sig, kid = ex
            fields = {
                "decision_id": str(decision_id),
                "action": str(action or ""),
                "payload_hash": str(ph or ""),
                "signature": str(sig or ""),
                "kid": str(kid or ""),
            }
            expected = entry_hash(prev_hash=str(prev_hash), fields=fields)
            if str(entry_h) != str(expected):
                return False

            prev = str(entry_h)
        return True

    def ping(self) -> bool:
        try:
            assert self._db is not None
            self._db.execute("SELECT 1")
            return True
        except Exception:
            return False

    # -----------------------------------------------------------------
    # Effect status (for async reconciliation / long-running effects)
    # -----------------------------------------------------------------

    def mark_effect_completed(self, envelope_id: str) -> None:
        assert self._db is not None
        self._db.execute(
            "INSERT INTO effect_status (envelope_id, status, updated_at_ms) VALUES (?,?,?) "
            "ON CONFLICT(envelope_id) DO UPDATE SET status=excluded.status, updated_at_ms=excluded.updated_at_ms;",
            (str(envelope_id), "completed", int(time.time() * 1000)),
        )
        self._db.commit()

    def mark_effect_failed(self, envelope_id: str) -> None:
        assert self._db is not None
        self._db.execute(
            "INSERT INTO effect_status (envelope_id, status, updated_at_ms) VALUES (?,?,?) "
            "ON CONFLICT(envelope_id) DO UPDATE SET status=excluded.status, updated_at_ms=excluded.updated_at_ms;",
            (str(envelope_id), "failed", int(time.time() * 1000)),
        )
        self._db.commit()

    def get_effect_status(self, envelope_id: str) -> str | None:
        assert self._db is not None
        row = self._db.execute(
            "SELECT status FROM effect_status WHERE envelope_id=? LIMIT 1;",
            (str(envelope_id),),
        ).fetchone()
        return str(row[0]) if row else None
