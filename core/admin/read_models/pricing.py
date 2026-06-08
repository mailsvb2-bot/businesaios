from __future__ import annotations

from typing import Any

from core.admin.read_models.pricing_support import iter_pricing_events, resolve_now_ms


def pricing_change_requests(event_store: Any, *, tenant_id: str = "default", limit: int = 20, now_ms: int | None = None) -> list[dict[str, Any]]:
    """Last pricing change requests with best-effort status."""
    if event_store is None or not hasattr(event_store, "iter_events"):
        return []

    end_ms = resolve_now_ms(now_ms=now_ms)
    applied: set[str] = set()
    try:
        for ev in iter_pricing_events(event_store, tenant_id=str(tenant_id), event_type="pricing_change_applied", end_ms=end_ms):
            p = ev.get("payload") or {}
            rid = str(p.get("request_id") or "").strip()
            if rid:
                applied.add(rid)
    except Exception:
        applied = set()

    reqs: list[dict[str, Any]] = []
    try:
        for ev in iter_pricing_events(event_store, tenant_id=str(tenant_id), event_type="pricing_change_requested", end_ms=end_ms):
            p = ev.get("payload") or {}
            rid = str(p.get("request_id") or "").strip()
            if not rid:
                continue
            reqs.append(
                {
                    "request_id": rid,
                    "plan_id": int(p.get("plan_id") or 0),
                    "new_price": int(p.get("new_price") or 0),
                    "suggested_pricing_version": str(p.get("suggested_pricing_version") or "").strip(),
                    "reason": str(p.get("reason") or "").strip(),
                    "requested_by": str(p.get("requested_by") or ev.get("user_id") or "").strip(),
                    "timestamp_ms": int(ev.get("timestamp_ms") or 0),
                }
            )
    except Exception:
        return []

    reqs.sort(key=lambda x: int(x.get("timestamp_ms") or 0), reverse=True)
    out: list[dict[str, Any]] = []
    for r in reqs:
        rid = str(r.get("request_id") or "")
        r["status"] = "applied" if rid in applied else "pending"
        out.append(r)
        if len(out) >= int(limit):
            break
    return out
