from __future__ import annotations

import time

from runtime.platform.utils.hash_chain import entry_hash, GENESIS
from runtime.platform.utils.canonical import payload_hash
from runtime.platform.postgres_port import PostgresPort
from observability.platform.observability.silent import swallow


class PostgresLedger:
    """Production DecisionLedger (Postgres).

    Exactly-once is enforced by PRIMARY KEY (decision_id) + atomic INSERT.
    Additionally we maintain a tamper-evident hash-chain table.
    """

    def __init__(self, dsn: str):
        self._dsn = str(dsn)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresLedger":
        self._port = PostgresPort(self._dsn, application_name="businesaios-ledger").__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)

    def _init_schema(self) -> None:
        assert self._port is not None
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS executed (
              decision_id TEXT PRIMARY KEY,
              executed_at_ms BIGINT NOT NULL,
              policy_id TEXT,
              action TEXT,
              payload_hash TEXT,
              signature TEXT,
              snapshot_id TEXT,
              state_hash TEXT,
              kid TEXT,
              correlation_id TEXT,
              envelope_version INT,
              state_schema_version INT,
              action_schema_version INT
            );
            """
        )
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS executed_chain (
              seq BIGSERIAL PRIMARY KEY,
              decision_id TEXT UNIQUE NOT NULL,
              prev_hash TEXT NOT NULL,
              entry_hash TEXT NOT NULL
            );
            """
        )
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS effect_status (
              envelope_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              updated_at_ms BIGINT NOT NULL
            );
            """
        )
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_executed_action ON executed(action);")
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_executed_policy ON executed(policy_id);")
        self._port.commit()

    def ping(self) -> bool:
        assert self._port is not None
        return self._port.ping()

    def is_executed(self, decision_id: str) -> bool:
        assert self._port is not None
        row = self._port.fetchone("SELECT 1 FROM executed WHERE decision_id=%s LIMIT 1;", (str(decision_id),))
        return bool(row)

    def already_executed(self, env) -> bool:
        decision = getattr(env, "decision", env)
        decision_id = str(getattr(decision, "decision_id", "") or "")
        if not decision_id:
            return False
        return self.is_executed(decision_id)

    @staticmethod
    def _chain_fields(*, decision_id: str, action: str, payload_hash_value: str, signature: str, kid: str) -> dict[str, str]:
        """Return the canonical ledger-chain fields used for write and verification.

        The field set must stay identical for try_mark_executed() and verify_chain().
        Changing either side independently breaks the tamper-evident proof chain.
        """
        return {
            "decision_id": str(decision_id),
            "action": str(action or ""),
            "payload_hash": str(payload_hash_value or ""),
            "signature": str(signature or ""),
            "kid": str(kid or ""),
        }

    def try_mark_executed(self, env) -> bool:
        assert self._port is not None
        decision = getattr(env, "decision", env)
        decision_id = str(getattr(decision, "decision_id", "")) or ""
        if not decision_id:
            return False

        try:
            row = self._port.fetchone("SELECT entry_hash FROM executed_chain ORDER BY seq DESC LIMIT 1;")
            prev = row[0] if row and row[0] else GENESIS

            executed_at_ms = int(time.time() * 1000)
            policy_id = str(getattr(decision, "policy_id", "") or "")
            action = str(getattr(decision, "action", "") or "")
            sig = str(getattr(env, "signature", "") or "")
            snapshot_id = str(getattr(decision, "snapshot_id", "") or "")
            state_hash = str(getattr(decision, "state_hash", "") or "")
            kid = str(getattr(env, "kid", "") or "")
            correlation_id = str(getattr(decision, "correlation_id", "") or "")
            envelope_version = int(getattr(env, "envelope_version", 1) or 1)
            state_schema_version = int(getattr(decision, "state_schema_version", 1) or 1)
            action_schema_version = int(getattr(decision, "action_schema_version", 1) or 1)

            ph = str(getattr(decision, "payload_hash", "") or "") or payload_hash(getattr(decision, "payload", {}))

            self._port.execute(
                """
                INSERT INTO executed (
                  decision_id, executed_at_ms, policy_id, action, payload_hash, signature,
                  snapshot_id, state_hash, kid, correlation_id, envelope_version,
                  state_schema_version, action_schema_version
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                """,
                (
                    decision_id,
                    executed_at_ms,
                    policy_id,
                    action,
                    ph,
                    sig,
                    snapshot_id,
                    state_hash,
                    kid,
                    correlation_id,
                    envelope_version,
                    state_schema_version,
                    action_schema_version,
                ),
            )

            eh = entry_hash(
                prev_hash=str(prev),
                fields=self._chain_fields(
                    decision_id=decision_id,
                    action=action,
                    payload_hash_value=ph,
                    signature=sig,
                    kid=kid,
                ),
            )
            self._port.execute(
                "INSERT INTO executed_chain (decision_id, prev_hash, entry_hash) VALUES (%s,%s,%s);",
                (decision_id, str(prev), str(eh)),
            )
            self._port.commit()
            return True
        except Exception:
            try:
                self._port.rollback()
            except Exception:
                swallow(__name__, 'runtime/platform/ledger/postgres_ledger.py')
            return False

    def mark_executed(self, decision_id: str) -> None:
        # reference-mode no-op; production uses try_mark_executed
        _ = self.is_executed(str(decision_id))

    def verify_chain(self) -> bool:
        assert self._port is not None
        rows = self._port.fetchall("SELECT decision_id, prev_hash, entry_hash FROM executed_chain ORDER BY seq ASC;")
        prev = GENESIS
        for decision_id, prev_hash, eh in rows:
            if str(prev_hash) != str(prev):
                return False
            row = self._port.fetchone(
                "SELECT action, payload_hash, signature, kid FROM executed WHERE decision_id=%s LIMIT 1;",
                (str(decision_id),),
            )
            if not row:
                return False
            action, ph, sig, kid = row
            calc = entry_hash(
                prev_hash=str(prev_hash),
                fields=self._chain_fields(
                    decision_id=str(decision_id),
                    action=str(action or ""),
                    payload_hash_value=str(ph or ""),
                    signature=str(sig or ""),
                    kid=str(kid or ""),
                ),
            )
            if str(calc) != str(eh):
                return False
            prev = str(eh)
        return True

    def mark_effect_completed(self, envelope_id: str) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute(
            """
            INSERT INTO effect_status(envelope_id, status, updated_at_ms)
            VALUES (%s,'completed',%s)
            ON CONFLICT (envelope_id) DO UPDATE SET status='completed', updated_at_ms=EXCLUDED.updated_at_ms;
            """,
            (str(envelope_id), now),
        )
        self._port.commit()

    def mark_effect_failed(self, envelope_id: str) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute(
            """
            INSERT INTO effect_status(envelope_id, status, updated_at_ms)
            VALUES (%s,'failed',%s)
            ON CONFLICT (envelope_id) DO UPDATE SET status='failed', updated_at_ms=EXCLUDED.updated_at_ms;
            """,
            (str(envelope_id), now),
        )
        self._port.commit()
