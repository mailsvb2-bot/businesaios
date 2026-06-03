from __future__ import annotations

"""Attribution: link lead → purchase.

This is deliberately minimal:
- store UTM (or source) from /start arguments into an event
- when purchase happens, attach last seen attribution window.

No network IO.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from collections.abc import Mapping


@dataclass(frozen=True)
class Attribution:
    source: str = ""
    campaign: str = ""
    content: str = ""
    term: str = ""
    medium: str = ""

    # optional ads ids (best-effort)
    platform: str = ""
    campaign_id: str = ""
    ad_id: str = ""

    # click/impression ids (gclid/fbclid/yclid/tclid, etc.)
    click_id: str = ""
    impression_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "source": str(self.source or ""),
            "campaign": str(self.campaign or ""),
            "content": str(self.content or ""),
            "term": str(self.term or ""),
            "medium": str(self.medium or ""),
            "platform": str(self.platform or ""),
            "campaign_id": str(self.campaign_id or ""),
            "ad_id": str(self.ad_id or ""),
            "click_id": str(self.click_id or ""),
            "impression_id": str(self.impression_id or ""),
        }


def parse_utm_from_args(args: str) -> Attribution:
    """Parse utm_* from a /start argument string.

    Supports formats:
      utm_source=x&utm_campaign=y
      utm_source=x;utm_campaign=y
    """
    a = str(args or "").strip()
    if not a:
        return Attribution()
    # Normalize separators
    a = a.replace(";", "&").replace("?", "&")
    parts = [p for p in a.split("&") if p]
    kv: dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = str(k or "").strip().lower()
        v = str(v or "").strip()
        kv[k] = v

    # UTM
    return Attribution(
        source=kv.get("utm_source", ""),
        medium=kv.get("utm_medium", ""),
        campaign=kv.get("utm_campaign", ""),
        content=kv.get("utm_content", ""),
        term=kv.get("utm_term", ""),
        # Ads ids (best-effort)
        platform=kv.get("platform", ""),
        campaign_id=kv.get("campaign_id", ""),
        ad_id=kv.get("ad_id", ""),
        # Click/impression ids (best-effort)
        click_id=(
            kv.get("gclid", "")
            or kv.get("fbclid", "")
            or kv.get("yclid", "")
            or kv.get("tclid", "")
            or kv.get("msclkid", "")
            or kv.get("click_id", "")
        ),
        impression_id=(kv.get("impression_id", "") or kv.get("imp_id", "")),
    )


def latest_attribution(event_store: Any, *, tenant_id: str, user_id: str, lookback_days: int = 30) -> Attribution | None:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return None
    # Best-effort scan (bounded): we only look at utm_set events in the window.
    import time

    now_ms = int(time.time() * 1000)
    start_ms = max(0, now_ms - int(lookback_days) * 24 * 3600 * 1000)
    latest = None
    latest_ts = -1
    for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=start_ms, event_type="utm_set@v1"):
        if str(ev.get("user_id") or "") != str(user_id):
            continue
        ts = int(ev.get("timestamp_ms") or 0)
        if ts < latest_ts:
            continue
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        latest_ts = ts
        latest = Attribution(
            source=str(payload.get("source") or ""),
            medium=str(payload.get("medium") or ""),
            campaign=str(payload.get("campaign") or ""),
            content=str(payload.get("content") or ""),
            term=str(payload.get("term") or ""),
            platform=str(payload.get("platform") or ""),
            campaign_id=str(payload.get("campaign_id") or ""),
            ad_id=str(payload.get("ad_id") or ""),
            click_id=str(payload.get("click_id") or ""),
            impression_id=str(payload.get("impression_id") or ""),
        )
    return latest
