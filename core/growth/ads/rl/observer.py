"""Automatic observe/tick for Ads RL.

Goal:
- When ads metrics are imported (event_type='ads_metrics_imported'), attach reward to
  the latest RL suggestion for that campaign and store an observed step.

Design:
- No "magic" subscriptions inside the EventStore.
- A small polling job can be run by a worker/cron.
- Idempotency via checkpoint event (tenant-aware).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol
from collections.abc import Iterable
from core.events.log import EventLog
from core.events.read_call import call_latest_event, call_latest_events
from core.observability.structured_logging import log_exception_throttled
from core.tenancy.scope import TenantId
from .contracts import AdsRLOptSpec, action_from_json

class _EventStore(Protocol):
    def iter_events(
        self,
        *,
        tenant_id: TenantId,
        start_ms: int,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> Iterable[dict]:
        ...

    def append_event(self, event: dict) -> None: ...

    # Optional accelerators implemented by sqlite/postgres backends.
    def latest_events(self, *, tenant_id: str, event_types: tuple[str, ...], limit: int = 2000) -> Iterable[dict]: ...  # type: ignore[override]
    def latest_event(self, *, tenant_id: str, event_type: str, user_id: str | None = None) -> dict | None: ...  # type: ignore[override]


@dataclass(frozen=True)
class ObserveTickResult:
    ok: bool
    status: str
    processed: int = 0
    skipped: int = 0
    last_ts_ms: int | None = None


def observe_tick_once(
    *,
    tenant_id: str,
    event_store: _EventStore,
    rl_service: Any,
    max_import_events: int = 500,
    lookback_hours_for_suggestion: int = 72,
) -> ObserveTickResult:
    """Scan new ads_metrics_imported events and attach rewards for the latest suggestion.

    This function is intentionally dumb and deterministic.

    Requirements:
    - RL suggestion handler stores spec snapshot in ads_rl_suggested@v1 payload.meta.spec.
    """

    now_ms = int(time.time() * 1000)
    start_ms = _load_checkpoint_ms(tenant_id=tenant_id, es=event_store)
    if start_ms is None:
        # conservative start: only recent events
        start_ms = now_ms - int(24 * 3600 * 1000)

    processed = 0
    skipped = 0
    last_ts: int | None = None

    for ev in event_store.iter_events(tenant_id=tenant_id, start_ms=int(start_ms), end_ms=None, event_type="ads_metrics_imported"):
        if processed + skipped >= int(max_import_events):
            break

        try:
            ts = int(ev.get("timestamp_ms") or 0)
        except Exception:
            ts = 0
        if ts <= int(start_ms):
            continue

        ok = _process_import_event(tenant_id=tenant_id, es=event_store, rl_service=rl_service, import_event=ev, now_ms=now_ms, lookback_hours=int(lookback_hours_for_suggestion))
        if ok:
            processed += 1
        else:
            skipped += 1
        last_ts = max(last_ts or 0, ts)

    if last_ts is not None:
        _save_checkpoint_ms(tenant_id=tenant_id, es=event_store, last_ts_ms=int(last_ts))
        return ObserveTickResult(ok=True, status="ok", processed=processed, skipped=skipped, last_ts_ms=int(last_ts))
    return ObserveTickResult(ok=True, status="no_new_events", processed=0, skipped=0, last_ts_ms=None)


def _process_import_event(*, tenant_id: str, es: _EventStore, rl_service: Any, import_event: dict, now_ms: int, lookback_hours: int) -> bool:
    p = import_event.get("payload") or {}
    ref = p.get("ref") or {}

    if str(ref.get("object_type") or "") != "campaign":
        return False

    platform = str(ref.get("platform") or "")
    campaign_id = str(ref.get("object_id") or "")
    if not platform or not campaign_id:
        return False

    sug = _latest_suggestion_for_campaign(tenant_id=tenant_id, es=es, platform=platform, campaign_id=campaign_id, now_ms=now_ms, lookback_hours=lookback_hours)
    if sug is None:
        return False

    payload = sug.get("payload") or {}
    meta = payload.get("meta") or {}
    spec_json = meta.get("spec")
    if not isinstance(spec_json, dict):
        return False

    try:
        spec = AdsRLOptSpec.from_json(spec_json)
    except Exception:
        return False

    # Ensure spec matches the campaign/platform we are observing.
    if str(spec.campaign_id) != campaign_id:
        return False
    if str(spec.platform) != platform:
        return False

    action_json = payload.get("action")
    if not isinstance(action_json, dict):
        return False

    action = action_from_json(action_json)
    policy_id = str(payload.get("policy_id") or "")
    if not policy_id:
        return False

    import_event_id = str(import_event.get("event_id") or "")
    observe_meta = {
        "observed_from_event_id": import_event_id,
        "import_ref": dict(ref),
        "import_metrics": dict(p.get("metrics") or {}),
        "suggested_action_key": str(payload.get("action_key") or ""),
        "suggested_ts_ms": int(sug.get("timestamp_ms") or 0),
    }
    try:
        out = rl_service.observe(
            tenant_id=str(tenant_id),
            user_id=None,
            spec=spec,
            policy_id=str(policy_id),
            action=action,
            meta=observe_meta,
        )
    except Exception:
        return False
    return bool((out or {}).get("status") == "ok")


def _latest_suggestion_for_campaign(*, tenant_id: str, es: _EventStore, platform: str, campaign_id: str, now_ms: int, lookback_hours: int) -> dict | None:
    start_ms = int(now_ms) - int(lookback_hours) * 3600 * 1000

    # Fast-path: backends may provide latest_events.
    latest = None
    if hasattr(es, "latest_events"):
        try:
            xs = list(call_latest_events(
                latest_fn=es.latest_events,
                tenant_id=str(tenant_id),
                event_types=("ads_rl_suggested@v1",),
                legacy_event_type="ads_rl_suggested@v1",
                limit=2000,
            ))
            for ev in xs:
                pp = ev.get("payload") or {}
                if str(pp.get("platform") or "") != str(platform):
                    continue
                if str(pp.get("campaign_id") or "") != str(campaign_id):
                    continue
                try:
                    ts = int(ev.get("timestamp_ms") or 0)
                except Exception:
                    ts = 0
                if ts < int(start_ms):
                    continue
                if latest is None or ts > int(latest.get("timestamp_ms") or 0):
                    latest = ev
            return latest
        except Exception as exc:
            log_exception_throttled(__name__, "ads_rl_observer_latest_events_failed", exc)

    # Fallback: scan iter_events window.
    for ev in es.iter_events(tenant_id=tenant_id, start_ms=int(start_ms), end_ms=None, event_type="ads_rl_suggested@v1"):
        pp = ev.get("payload") or {}
        if str(pp.get("platform") or "") != str(platform):
            continue
        if str(pp.get("campaign_id") or "") != str(campaign_id):
            continue
        try:
            ts = int(ev.get("timestamp_ms") or 0)
        except Exception:
            ts = 0
        if latest is None or ts > int(latest.get("timestamp_ms") or 0):
            latest = ev
    return latest


def _load_checkpoint_ms(*, tenant_id: str, es: _EventStore) -> int | None:
    if hasattr(es, "latest_event"):
        try:
            ev = call_latest_event(
                latest_fn=es.latest_event,
                tenant_id=str(tenant_id),
                user_id=None,
                event_types=("ads_rl_observer_checkpoint@v1",),
                legacy_event_type="ads_rl_observer_checkpoint@v1",
            )
            if ev:
                payload = ev.get("payload") or {}
                v = payload.get("last_ts_ms")
                return int(v) if v is not None else None
        except Exception:
            return None

    # fallback: scan for latest checkpoint in the last 90 days
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 90 * 24 * 3600 * 1000
    latest = None
    for ev in es.iter_events(tenant_id=tenant_id, start_ms=int(start_ms), end_ms=None, event_type="ads_rl_observer_checkpoint@v1"):
        latest = ev
    if latest:
        payload = latest.get("payload") or {}
        try:
            return int(payload.get("last_ts_ms") or 0)
        except Exception:
            return None
    return None


def _save_checkpoint_ms(*, tenant_id: str, es: _EventStore, last_ts_ms: int) -> None:
    # Use tenant-scoped EventLog; direct store writes are forbidden by release gate.
    EventLog(es, tenant=str(tenant_id)).append(
        {
            "tenant_id": str(tenant_id),
            "user_id": "",
            "source": "ads_rl_observer",
            "event_type": "ads_rl_observer_checkpoint@v1",
            "timestamp_ms": int(time.time() * 1000),
            "payload": {"last_ts_ms": int(last_ts_ms)},
        }
    )
