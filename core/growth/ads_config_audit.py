from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Protocol

from core.growth.ads_config_fingerprint import ads_config_fingerprint

class EventStore(Protocol):
    def append(self, *, tenant_id: str, user_id: Optional[str], event_type: str, payload: Dict[str, Any]) -> None: ...
    def latest_events(self, *, tenant_id: str, event_type: str, limit: int = 50) -> Iterable[Dict[str, Any]]: ...

class AdsConfigAudit:
    EVENT_TYPE = "ads_config_fingerprint_changed"

    def __init__(self, *, store: EventStore, entitlements_provider: Any):
        self._store = store
        self._ent = entitlements_provider

    def ensure_audited(self, *, tenant_id: str) -> str:
        ent = self._ent.get_ads_entitlements(tenant_id)
        lim = self._ent.get_daily_limits(tenant_id)
        fp = ads_config_fingerprint(ads_entitlements=ent, daily_limits=lim)

        last_fp = None
        for ev in self._store.latest_events(tenant_id=tenant_id, event_type=self.EVENT_TYPE, limit=10):
            last_fp = (ev.get("payload") or {}).get("config_fp")
            if last_fp:
                break
        if last_fp != fp:
            self._store.append(
                tenant_id=tenant_id,
                user_id=None,
                event_type=self.EVENT_TYPE,
                payload={
                    "config_fp": fp,
                    "prev_fp": last_fp,
                    "changed_at_iso": datetime.now(timezone.utc).isoformat(),
                    "mode": getattr(ent.mode, "value", str(ent.mode)),
                },
            )
        return fp
