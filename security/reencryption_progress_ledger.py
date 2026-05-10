from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.platform.security_sqlite_stores import SQLiteReencryptionProgressLedgerBackend

CANON_REENCRYPTION_PROGRESS_LEDGER = True


@dataclass(frozen=True)
class ReencryptionProgressEvent:
    job_id: str
    event_kind: str
    secret_ref: str | None
    ok: bool
    payload: dict[str, Any]


class SQLiteReencryptionProgressLedger:
    """Security-facing reencryption progress facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteReencryptionProgressLedgerBackend(db_path, ReencryptionProgressEvent)

    def append(self, event: ReencryptionProgressEvent) -> None:
        self._backend.append(event)

    def latest_for_job(self, job_id: str, *, limit: int = 100) -> tuple[ReencryptionProgressEvent, ...]:
        return self._backend.latest_for_job(job_id, limit=limit)


__all__ = ['CANON_REENCRYPTION_PROGRESS_LEDGER', 'ReencryptionProgressEvent', 'SQLiteReencryptionProgressLedger']
