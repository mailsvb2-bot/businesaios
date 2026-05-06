from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueueStorePolicy:
    """Canonical operational defaults for runtime queue stores.

    Infrastructure-only policy surface. This centralizes queue-store knobs so
    storage layers do not accumulate hidden fallback behavior or duplicated
    literals across in-memory, JSON, and SQLite implementations.
    """

    default_due_limit: int = 100
    default_claim_lease_seconds: int = 60
    default_purge_limit: int = 1000
    default_sqlite_busy_timeout_ms: int = 5000
    min_sqlite_busy_timeout_ms: int = 100
    wal_checkpoint_on_close: bool = True

    def normalize_due_limit(self, value: int) -> int:
        return max(0, int(value))

    def normalize_claim_lease_seconds(self, value: int) -> int:
        return max(1, int(value))

    def normalize_purge_limit(self, value: int) -> int:
        return max(1, int(value))

    def normalize_sqlite_busy_timeout_ms(self, value: int) -> int:
        return max(self.min_sqlite_busy_timeout_ms, int(value))


DEFAULT_QUEUE_STORE_POLICY = QueueStorePolicy()


__all__ = ["DEFAULT_QUEUE_STORE_POLICY", "QueueStorePolicy"]
