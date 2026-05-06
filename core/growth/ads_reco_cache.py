from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Protocol

class EventStore(Protocol):
    def append(self, *, tenant_id: str, user_id: Optional[str], event_type: str, payload: Dict[str, Any]) -> None: ...
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 2000) -> Iterable[Dict[str, Any]]: ...

@dataclass(frozen=True)
class CachedRecommendation:
    rec_id: str
    expires_at_iso: str
    payload: Dict[str, Any]

class AdsRecommendationCache:
    EVENT_TYPE = "ads_reco_cached"

    def __init__(self, *, store: EventStore, ttl_minutes: int = 120, scan_limit: int = 2000):
        self._store = store
        self._ttl = int(ttl_minutes)
        self._scan_limit = int(scan_limit)

    def put(self, *, tenant_id: str, user_id: Optional[str], rec_id: str, rec_payload: Dict[str, Any], config_fp: Optional[str]) -> None:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self._ttl)
        self._store.append(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=self.EVENT_TYPE,
            payload={"rec_id": rec_id, "expires_at_iso": exp.isoformat(), "config_fp": config_fp, "rec": rec_payload},
        )

    def get(self, *, tenant_id: str, rec_id: str, expected_config_fp: Optional[str]) -> Optional[CachedRecommendation]:
        now = datetime.now(timezone.utc)
        for ev in self._store.latest_events(tenant_id=tenant_id, event_type=self.EVENT_TYPE, limit=self._scan_limit):
            p = ev.get("payload") or {}
            if str(p.get("rec_id")) != rec_id:
                continue
            exp_s = p.get("expires_at_iso")
            if not exp_s:
                continue
            exp = _parse_iso(exp_s)
            if now >= exp:
                continue
            if expected_config_fp is not None and p.get("config_fp") != expected_config_fp:
                continue
            rec = p.get("rec")
            if not isinstance(rec, dict):
                continue
            return CachedRecommendation(rec_id=rec_id, expires_at_iso=exp_s, payload=rec)
        return None

def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
