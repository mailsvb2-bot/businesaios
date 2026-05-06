from __future__ import annotations

import json
import time
import uuid

from runtime.platform.postgres_port import PostgresPort


class PostgresPaymentOutbox:
    """Durable job outbox for external payment reconciliations (Postgres)."""

    def __init__(self, dsn: str):
        self._dsn = str(dsn)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresPaymentOutbox":
        self._port = PostgresPort(self._dsn, application_name="businesaios-payment-outbox").__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)

    def _init_schema(self) -> None:
        assert self._port is not None
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_outbox (
              id TEXT PRIMARY KEY,
              dedupe_key TEXT UNIQUE,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at_ms BIGINT NOT NULL,
              updated_at_ms BIGINT NOT NULL,
              run_after_ms BIGINT NOT NULL,
              attempts INT NOT NULL DEFAULT 0,
              last_error TEXT
            );
            """
        )
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_payment_outbox_status_after ON payment_outbox(status, run_after_ms);")
        self._port.execute("""
            CREATE TABLE IF NOT EXISTS payment_terminal (
              external_id TEXT PRIMARY KEY,
              terminal_status TEXT NOT NULL,
              emitted_at_ms BIGINT NOT NULL,
              notification_id TEXT,
              event TEXT
            );
            """)
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_payment_terminal_status ON payment_terminal(terminal_status);")
        self._port.commit()

    def ping(self) -> bool:
        assert self._port is not None
        return self._port.ping()

    def enqueue_once(self, *, dedupe_key: str, payload: dict) -> str:
        assert self._port is not None
        now = int(time.time() * 1000)
        jid = str(uuid.uuid4())
        self._port.execute(
            """
            INSERT INTO payment_outbox(id, dedupe_key, status, payload_json, created_at_ms, updated_at_ms, run_after_ms, attempts)
            VALUES (%s,%s,'pending',%s,%s,%s,%s,0)
            ON CONFLICT (dedupe_key) DO NOTHING;
            """,
            (jid, str(dedupe_key), json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")), now, now, now),
        )
        self._port.commit()
        row = self._port.fetchone("SELECT id FROM payment_outbox WHERE dedupe_key=%s LIMIT 1;", (str(dedupe_key),))
        return str(row[0]) if row else jid

    def list_pending(self, *, limit: int = 50) -> list[dict]:
        assert self._port is not None
        now = int(time.time() * 1000)
        rows = self._port.fetchall(
            "SELECT id, dedupe_key, payload_json, attempts, run_after_ms FROM payment_outbox "
            "WHERE status='pending' AND run_after_ms <= %s ORDER BY run_after_ms ASC LIMIT %s;",
            (now, int(limit)),
        )
        out: list[dict] = []
        for r in rows:
            out.append({"id": r[0], "dedupe_key": r[1], "payload": json.loads(r[2] or "{}"), "attempts": int(r[3] or 0), "run_after_ms": int(r[4] or 0)})
        return out

    def claim(self, job_id: str) -> bool:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute("UPDATE payment_outbox SET status='inflight', updated_at_ms=%s WHERE id=%s AND status='pending';", (now, str(job_id)))
        self._port.commit()
        row = self._port.fetchone("SELECT status FROM payment_outbox WHERE id=%s LIMIT 1;", (str(job_id),))
        return bool(row and row[0] == "inflight")

    def mark_delivered(self, job_id: str) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute("UPDATE payment_outbox SET status='delivered', updated_at_ms=%s WHERE id=%s;", (now, str(job_id)))
        self._port.commit()

    def schedule_retry(self, job_id: str, *, after_ms: int, error: str | None = None) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        run_after = now + int(after_ms)
        self._port.execute(
            "UPDATE payment_outbox SET status='pending', updated_at_ms=%s, run_after_ms=%s, attempts=attempts+1, last_error=%s WHERE id=%s;",
            (now, run_after, (str(error) if error else None), str(job_id)),
        )
        self._port.commit()

    def move_to_dead_letter(self, job_id: str, *, error: str | None = None) -> None:
        assert self._port is not None
        now = int(time.time() * 1000)
        self._port.execute(
            "UPDATE payment_outbox SET status='dead', updated_at_ms=%s, last_error=%s WHERE id=%s;",
            (now, (str(error) if error else None), str(job_id)),
        )
        self._port.commit()

    # ---- terminal idempotency (heavy-load safe) ----

    def terminal_status(self, external_id: str) -> str | None:
        assert self._port is not None
        row = self._port.fetchone("SELECT terminal_status FROM payment_terminal WHERE external_id=%s LIMIT 1;", (str(external_id),))
        return str(row[0]) if row and row[0] is not None else None

    def try_mark_terminal_emitted(
        self,
        *,
        external_id: str,
        terminal_status: str,
        notification_id: str | None = None,
        event: str | None = None,
    ) -> bool:
        """Idempotently mark terminal outcome emission.

        Returns True iff this call created the marker.
        """
        assert self._port is not None
        now = int(time.time() * 1000)
        row = self._port.fetchone(
            """
            INSERT INTO payment_terminal(external_id, terminal_status, emitted_at_ms, notification_id, event)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (external_id) DO NOTHING
            RETURNING external_id;
            """,
            (str(external_id), str(terminal_status), now, (str(notification_id) if notification_id else None), (str(event) if event else None)),
        )
        self._port.commit()
        return bool(row)
