from __future__ import annotations

import time
from typing import Any

from runtime.platform.config.env_flags import env_int
from runtime.platform.postgres_port import PostgresPort


class PostgresOutbox:
    """Postgres runtime outbox with sqlite-compatible runtime semantics."""

    def __init__(self, dsn: str):
        self._dsn = str(dsn)
        self._port: PostgresPort | None = None
        try:
            self._lease_ms = int(env_int("OUTBOX_LEASE_MS", 60_000, lo=5_000, hi=10 * 60_000))
        except (TypeError, ValueError):
            self._lease_ms = 60_000
        self._lease_ms = max(5_000, min(10 * 60_000, int(self._lease_ms)))

    def __enter__(self) -> PostgresOutbox:
        self._port = PostgresPort(self._dsn, application_name="businesaios-outbox").__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)

    def _init_schema(self) -> None:
        assert self._port is not None
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
              decision_id TEXT PRIMARY KEY,
              correlation_id TEXT NOT NULL,
              action TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at_ms BIGINT NOT NULL,
              delivered_at_ms BIGINT,
              claimed_at_ms BIGINT,
              next_attempt_at_ms BIGINT,
              retry_count INT NOT NULL DEFAULT 0,
              status TEXT NOT NULL
            );
            """
        )
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, created_at_ms);")
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_outbox_next_attempt ON outbox(status, next_attempt_at_ms);")
        self._port.commit()

    def ping(self) -> bool:
        assert self._port is not None
        return self._port.ping()

    def enqueue_once(self, *, decision_id: str, correlation_id: str, action: str, payload_json: str) -> bool:
        assert self._port is not None
        now = int(time.time() * 1000)
        row = self._port.fetchone(
            """
            INSERT INTO outbox(decision_id, correlation_id, action, payload_json, created_at_ms, next_attempt_at_ms, retry_count, status)
            VALUES (%s,%s,%s,%s,%s,%s,0,'pending')
            ON CONFLICT (decision_id) DO NOTHING
            RETURNING decision_id;
            """,
            (str(decision_id), str(correlation_id), str(action), str(payload_json), now, now),
        )
        self._port.commit()
        return bool(row and row[0] == str(decision_id))

    def _reap_stale_delivering(self) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        stale_cutoff = now - int(self._lease_ms)
        self._port.execute(
            "UPDATE outbox SET status='pending', claimed_at_ms=NULL WHERE status='delivering' AND claimed_at_ms IS NOT NULL AND claimed_at_ms<=%s;",
            (stale_cutoff,),
        )
        self._port.commit()

    def has_pending(self, decision_id: str) -> bool:
        assert self._port is not None
        row = self._port.fetchone(
            "SELECT 1 FROM outbox WHERE decision_id=%s AND status IN ('pending','delivering') LIMIT 1;",
            (str(decision_id),),
        )
        return bool(row)

    def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        assert self._port is not None
        self._reap_stale_delivering()
        rows = self._port.fetchall(
            "SELECT decision_id, correlation_id, action, payload_json, created_at_ms, status, retry_count, next_attempt_at_ms, claimed_at_ms "
            "FROM outbox WHERE status IN ('pending','delivering') ORDER BY created_at_ms ASC LIMIT %s;",
            (int(limit),),
        )
        return [
            {
                "decision_id": r[0],
                "correlation_id": r[1],
                "action": r[2],
                "payload_json": r[3],
                "created_at_ms": int(r[4]),
                "status": r[5],
                "retry_count": int(r[6] or 0),
                "next_attempt_at_ms": int(r[7] or 0) if r[7] is not None else None,
                "claimed_at_ms": int(r[8] or 0) if r[8] is not None else None,
            }
            for r in rows
        ]

    def list_claimable(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.list_pending(limit=limit)

    def claim(self, decision_id: str) -> bool:
        assert self._port is not None
        now = int(time.time() * 1000)
        stale_cutoff = now - int(self._lease_ms)
        row = self._port.fetchone(
            """
            UPDATE outbox SET status='delivering', claimed_at_ms=%s
            WHERE decision_id=%s AND (
                (status='pending' AND (next_attempt_at_ms IS NULL OR next_attempt_at_ms<=%s)) OR
                (status='delivering' AND claimed_at_ms IS NOT NULL AND claimed_at_ms<=%s)
            )
            RETURNING decision_id;
            """,
            (now, str(decision_id), now, stale_cutoff),
        )
        self._port.commit()
        return bool(row and row[0] == str(decision_id))

    def mark_delivered(self, decision_id: str) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute(
            "UPDATE outbox SET status='delivered', delivered_at_ms=%s, claimed_at_ms=NULL WHERE decision_id=%s AND status IN ('pending','delivering');",
            (now, str(decision_id)),
        )
        self._port.commit()

    def schedule_retry(self, decision_id: str, next_attempt_at_ms: int) -> None:
        assert self._port is not None
        row = self._port.fetchone("SELECT retry_count FROM outbox WHERE decision_id=%s LIMIT 1;", (str(decision_id),))
        current = int(row[0] or 0) if row else 0
        if current >= 5:
            self.move_to_dead_letter(decision_id)
            return
        self._port.execute(
            "UPDATE outbox SET status='pending', next_attempt_at_ms=%s, retry_count=retry_count+1, claimed_at_ms=NULL WHERE decision_id=%s AND status IN ('pending','delivering');",
            (int(next_attempt_at_ms), str(decision_id)),
        )
        self._port.commit()

    def move_to_dead_letter(self, decision_id: str) -> None:
        assert self._port is not None
        self._port.execute(
            "UPDATE outbox SET status='dead', claimed_at_ms=NULL WHERE decision_id=%s AND status IN ('pending','delivering');",
            (str(decision_id),),
        )
        self._port.commit()

    def status(self, decision_id: str) -> str | None:
        assert self._port is not None
        row = self._port.fetchone("SELECT status FROM outbox WHERE decision_id=%s LIMIT 1;", (str(decision_id),))
        return str(row[0]) if row else None
