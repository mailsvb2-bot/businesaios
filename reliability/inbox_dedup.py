from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading

from core.tenancy.normalization import require_tenant_id


CANON_INBOX_DEDUP = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class InboxReceipt:
    tenant_id: str
    source: str
    dedupe_key: str
    received_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=utc_now)
    payload_digest: str | None = None

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.source or "").strip():
            raise ValueError("source is required")
        if not str(self.dedupe_key or "").strip():
            raise ValueError("dedupe_key is required")
        if self.received_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.expires_at <= self.received_at:
            raise ValueError("expires_at must be > received_at")


class InboxDedup:
    def __init__(self) -> None:
        self._receipts: dict[tuple[str, str, str], InboxReceipt] = {}
        self._lock = threading.RLock()

    def accept(
        self,
        *,
        tenant_id: str,
        source: str,
        dedupe_key: str,
        ttl_seconds: int = 3600,
        payload_digest: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        tid = require_tenant_id(tenant_id)
        src = str(source).strip()
        dedupe = str(dedupe_key).strip()
        if not src:
            raise ValueError("source is required")
        if not dedupe:
            raise ValueError("dedupe_key is required")

        moment = now or utc_now()
        cache_key = (tid, src, dedupe)
        with self._lock:
            existing = self._receipts.get(cache_key)
            if existing is not None and moment < existing.expires_at:
                return False

            receipt = InboxReceipt(
                tenant_id=tid,
                source=src,
                dedupe_key=dedupe,
                received_at=moment,
                expires_at=moment + timedelta(seconds=max(1, int(ttl_seconds))),
                payload_digest=None if payload_digest is None else str(payload_digest),
            )
            receipt.validate()
            self._receipts[cache_key] = receipt
            return True

    def purge_expired(self, *, now: datetime | None = None) -> int:
        moment = now or utc_now()
        removed = 0
        with self._lock:
            for cache_key, receipt in list(self._receipts.items()):
                if moment >= receipt.expires_at:
                    self._receipts.pop(cache_key, None)
                    removed += 1
        return removed


__all__ = [
    "CANON_INBOX_DEDUP",
    "InboxDedup",
    "InboxReceipt",
]
