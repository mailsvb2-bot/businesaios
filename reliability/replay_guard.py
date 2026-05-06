from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading

from core.tenancy.normalization import require_tenant_id


CANON_REPLAY_GUARD = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReplayVerdict:
    allowed: bool
    reason: str
    last_sequence_no: int | None = None
    observed_at: datetime = field(default_factory=utc_now)
    payload_digest_matches: bool | None = None


class ReplayGuard:
    def __init__(self) -> None:
        self._last_seen: dict[tuple[str, str], tuple[int, str | None]] = {}
        self._lock = threading.RLock()

    def evaluate(
        self,
        *,
        tenant_id: str,
        stream_id: str,
        sequence_no: int,
        payload_digest: str | None = None,
    ) -> ReplayVerdict:
        tid = require_tenant_id(tenant_id)
        stream = str(stream_id).strip()
        if not stream:
            raise ValueError("stream_id is required")
        seq = int(sequence_no)
        if seq < 0:
            raise ValueError("sequence_no must be >= 0")

        cache_key = (tid, stream)
        digest = None if payload_digest is None else str(payload_digest)
        with self._lock:
            last = self._last_seen.get(cache_key)
            if last is None:
                self._last_seen[cache_key] = (seq, digest)
                return ReplayVerdict(allowed=True, reason="first_observation")

            last_seq, last_digest = last
            digest_matches = None if digest is None or last_digest is None else digest == last_digest
            if seq < last_seq:
                return ReplayVerdict(
                    allowed=False,
                    reason="out_of_order_or_replay",
                    last_sequence_no=last_seq,
                    payload_digest_matches=digest_matches,
                )
            if seq == last_seq:
                return ReplayVerdict(
                    allowed=False,
                    reason="duplicate_sequence",
                    last_sequence_no=last_seq,
                    payload_digest_matches=digest_matches,
                )

            self._last_seen[cache_key] = (seq, digest)
            return ReplayVerdict(
                allowed=True,
                reason="advanced",
                last_sequence_no=last_seq,
                payload_digest_matches=digest_matches,
            )


__all__ = [
    "CANON_REPLAY_GUARD",
    "ReplayGuard",
    "ReplayVerdict",
]
