from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.spend_ledger_policy import DEFAULT_SPEND_LEDGER_POLICY, SpendLedgerPolicy
from core.events.read_call import call_iter_events, call_latest_events


def _day_start_ms(ts_ms: int) -> int:
    return ts_ms - (ts_ms % 86_400_000)


@dataclass
class EventStoreSpendLedger:
    """Best-effort spend ledger based on imported ads metrics events.

    Safety stance:
    - If we cannot confidently compute spend for the current day, we return a
      very large value to force guardrails to block writes.

    Assumes `ads_metrics_imported` events with payload:
      {ref: {platform, object_type, object_id, ...}, metrics: {spend: ...}}
    """

    event_store: Any
    cache_ttl_s: int = 5
    max_scan: int = 1000
    policy: SpendLedgerPolicy = DEFAULT_SPEND_LEDGER_POLICY

    _cache_until: float = float(0)
    _cache: dict[str, float] = None  # type: ignore

    def _load_today(self, *, tenant_id: str) -> dict[str, float]:
        now_ms = int(time.time() * 1000)
        start_ms = _day_start_ms(now_ms)

        # event_store API differs by backend. We rely on the canonical helper:
        # latest_events(tenant_id=..., event_types=..., limit=...)
        try:
            events = call_latest_events(
                latest_fn=self.event_store.latest_events,
                tenant_id=str(tenant_id),
                event_types=("ads_metrics_imported",),
                limit=int(self.max_scan),
            )
        except Exception:
            return {"__uncertain__": float(self.policy.uncertainty_marker)}

        totals: dict[str, float] = {"total": float(self.policy.zero_value)}
        uncertain = False
        earliest_ts = None

        for e in events:
            try:
                ts = int(e.get("timestamp_ms") or 0)
            except Exception:
                ts = 0
            if earliest_ts is None or ts < earliest_ts:
                earliest_ts = ts
            if ts < start_ms:
                continue
            payload = e.get("payload") or {}
            ref = payload.get("ref") or {}
            metrics = payload.get("metrics") or {}

            spend = metrics.get("spend")
            try:
                spend_f = float(spend or self.policy.zero_value)
            except Exception:
                spend_f = float(self.policy.zero_value)

            totals["total"] += spend_f

            platform = str(ref.get("platform") or "")
            if platform:
                totals[f"platform:{platform}"] = totals.get(f"platform:{platform}", float(self.policy.zero_value)) + spend_f
            if str(ref.get("object_type") or "") == "campaign":
                cid = str(ref.get("object_id") or "")
                if platform and cid:
                    k = f"campaign:{platform}:{cid}"
                    totals[k] = totals.get(k, float(self.policy.zero_value)) + spend_f

        # If we hit scan cap and the earliest event is still within today,
        # we may have missed spend -> treat as uncertain.
        if len(events) >= int(self.max_scan) and earliest_ts is not None and int(earliest_ts) >= start_ms:
            uncertain = True

        if uncertain:
            totals["__uncertain__"] = float(self.policy.uncertainty_marker)
        return totals

    def _get_cached(self, *, tenant_id: str) -> dict[str, float]:
        now = time.time()
        if self._cache is not None and now < self._cache_until:
            return self._cache
        self._cache = self._load_today(tenant_id=tenant_id)
        self._cache_until = now + float(self.cache_ttl_s)
        return self._cache

    def get_spend_today_total(self, *, tenant_id: str) -> float:
        d = self._get_cached(tenant_id=tenant_id)
        if d.get("__uncertain__"):
            return float("inf")
        return float(d.get("total") or self.policy.zero_value)

    def get_spend_today_platform(self, *, tenant_id: str, platform: str) -> float:
        d = self._get_cached(tenant_id=tenant_id)
        if d.get("__uncertain__"):
            return float("inf")
        return float(d.get(f"platform:{platform}") or self.policy.zero_value)

    def get_spend_today_campaign(self, *, tenant_id: str, platform: str, campaign_id: str) -> float:
        d = self._get_cached(tenant_id=tenant_id)
        if d.get("__uncertain__"):
            return float("inf")
        return float(d.get(f"campaign:{platform}:{campaign_id}") or self.policy.zero_value)



    def spend_minor_range(self, *, tenant_id: str, start_ms: int, end_ms: int) -> int:
        """Return spend in minor units for an arbitrary time range.

        Uses the canonical latest_events read API when available and falls back to
        iter_events(event_type=...) for stores that do not support event_types.
        Returns a huge blocking value when confidence is insufficient.
        """
        tid = str(tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required")
        start_ms = int(start_ms)
        end_ms = int(end_ms)
        try:
            if hasattr(self.event_store, "latest_events"):
                events = call_latest_events(
                    latest_fn=self.event_store.latest_events,
                    tenant_id=tid,
                    event_types=("ads_metrics_imported",),
                    limit=int(self.max_scan),
                )
            else:
                events = list(
                    call_iter_events(
                        iter_fn=self.event_store.iter_events,
                        tenant_id=tid,
                        event_types=("ads_metrics_imported",),
                        start_ms=start_ms,
                        end_ms=end_ms,
                        limit=int(self.max_scan),
                        user_id=None,
                    )
                )
        except Exception:
            return int(self.policy.block_minor_units)

        total_major = float(self.policy.zero_value)
        seen = 0
        for e in events or []:
            try:
                ts = int((e or {}).get("timestamp_ms") or 0)
            except Exception:
                ts = 0
            if ts < start_ms or ts > end_ms:
                continue
            payload = (e or {}).get("payload") or {}
            metrics = payload.get("metrics") or {}
            try:
                total_major += float(metrics.get("spend") or self.policy.zero_value)
            except Exception:
                continue
            seen += 1
        if seen >= int(self.max_scan):
            return int(self.policy.block_minor_units)
        return int(round(float(total_major) * int(self.policy.major_to_minor_multiplier)))

    def today(self, *, tenant_id: str) -> dict[str, float]:
        """Return today's spend totals (major units).

        This is a pure read-model derived from ads_metrics_imported events.
        Result shape matches _load_today.
        """
        return dict(self._get_cached(tenant_id=str(tenant_id)) or {})

    def today_spend_minor(self, *, tenant_id: str) -> int:
        """Return today's spend in minor units (best-effort).

        We interpret imported metrics 'spend' as major units (e.g., RUB),
        and convert to minor by *100.
        If uncertain, return a huge number to force guardrails to block writes.
        """
        data = self.today(tenant_id=str(tenant_id))
        if not isinstance(data, dict):
            return int(self.policy.block_minor_units)
        if data.get("__uncertain__"):
            return int(self.policy.block_minor_units)
        try:
            major = float(data.get("total") or self.policy.zero_value)
        except Exception:
            major = float(self.policy.zero_value)
        return int(round(float(major) * int(self.policy.major_to_minor_multiplier)))

