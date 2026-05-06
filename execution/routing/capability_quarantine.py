from __future__ import annotations
import time
from dataclasses import dataclass
CANON_CAPABILITY_QUARANTINE = True
@dataclass(frozen=True)
class QuarantineRecord:
    route_key: str
    reason: str
    until_ts: float
    @property
    def active(self) -> bool:
        return time.time() < float(self.until_ts)
class CapabilityQuarantine:
    def __init__(self) -> None:
        self._records: dict[str, QuarantineRecord] = {}
    def quarantine(self, *, route_key: str, reason: str, ttl_seconds: float) -> None:
        now = time.time()
        self._records[str(route_key)] = QuarantineRecord(
            route_key=str(route_key),
            reason=str(reason),
            until_ts=now + max(0.0, float(ttl_seconds)),
        )
    def get(self, *, route_key: str) -> QuarantineRecord | None:
        record = self._records.get(str(route_key))
        if record is None:
            return None
        if not record.active:
            self._records.pop(str(route_key), None)
            return None
        return record
    def is_quarantined(self, *, route_key: str) -> bool:
        return self.get(route_key=route_key) is not None
