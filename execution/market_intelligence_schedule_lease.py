from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import os
import uuid
from threading import RLock
from typing import Any

from governance.persistence_codec import atomic_write_json, read_json_or_default


CANON_MARKET_INTELLIGENCE_SCHEDULE_LEASE = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _store_path() -> Path:
    explicit = _text(os.getenv("BUSINESAIOS_MARKET_INTELLIGENCE_SCHEDULE_LEASE_PATH"))
    if explicit:
        return Path(explicit)
    data_dir = _text(os.getenv("DATA_DIR"), default=".runtime_data")
    return Path(data_dir) / "runtime" / "market_intelligence_schedule_lease.json"


@dataclass(frozen=True)
class ScheduleLeaseRecord:
    lease_key: str
    owner_id: str
    acquired_at: str
    expires_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "lease_key": self.lease_key,
            "owner_id": self.owner_id,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }


class PersistentMarketIntelligenceScheduleLeaseStore:
    """Best-effort duplicate suppression for recurring runs. No planning logic."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else _store_path()
        self._lock = RLock()
        self._state: dict[str, Any] = {"leases": {}}
        self._load()

    def allocate_owner_id(self) -> str:
        return f"mi-scheduler:{uuid.uuid4().hex}"

    def try_acquire(self, *, lease_key: str, owner_id: str, ttl_seconds: int) -> bool:
        with self._lock:
            self._purge_expired_locked()
            current = dict(self._state.get("leases", {})).get(lease_key)
            now = _utc_now()
            if isinstance(current, dict):
                expires_at = self._parse_dt(current.get("expires_at"))
                if expires_at is not None and expires_at > now and _text(current.get("owner_id")) != _text(owner_id):
                    return False
            record = ScheduleLeaseRecord(
                lease_key=_text(lease_key),
                owner_id=_text(owner_id),
                acquired_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=max(1, int(ttl_seconds)))).isoformat(),
            )
            self._state.setdefault("leases", {})[lease_key] = record.as_dict()
            self._flush()
            return True

    def release(self, *, lease_key: str, owner_id: str) -> None:
        with self._lock:
            current = dict(self._state.get("leases", {})).get(lease_key)
            if not isinstance(current, dict):
                return
            if _text(current.get("owner_id")) != _text(owner_id):
                return
            self._state.setdefault("leases", {}).pop(lease_key, None)
            self._flush()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._purge_expired_locked()
            return {"leases": dict(self._state.get("leases", {}))}

    def _purge_expired_locked(self) -> None:
        now = _utc_now()
        leases = dict(self._state.get("leases", {}))
        keep: dict[str, Any] = {}
        changed = False
        for key, value in leases.items():
            expires_at = self._parse_dt(dict(value).get("expires_at"))
            if expires_at is None or expires_at <= now:
                changed = True
                continue
            keep[str(key)] = dict(value)
        if changed:
            self._state["leases"] = keep
            self._flush()

    @staticmethod
    def _parse_dt(value: object) -> datetime | None:
        text = _text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default=self._state)
        if isinstance(raw, dict):
            self._state = {"leases": dict(raw.get("leases", {}))}

    def _flush(self) -> None:
        atomic_write_json(self._path, self._state)


__all__ = [
    "CANON_MARKET_INTELLIGENCE_SCHEDULE_LEASE",
    "PersistentMarketIntelligenceScheduleLeaseStore",
    "ScheduleLeaseRecord",
]
