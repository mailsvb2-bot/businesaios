from __future__ import annotations

from typing import Any

from core.admin.read_models.pricing_support import iter_pricing_events, resolve_now_ms

# Current governed-pricing facts plus legacy compatibility.
_REQUESTED = ("admin_pricing_change_requested", "pricing_change_requested")
_APPLIED = ("admin_pricing_change_applied", "pricing_change_applied")
_REJECTED = ("admin_pricing_change_rejected", "pricing_change_rejected")


def _request_ids(event_store: Any, *, tenant_id: str,
                 event_types: tuple[str, ...], end_ms: int) -> set[str]:
    ids: set[str] = set()
    for event_type in event_types:
        try:
            for event in iter_pricing_events(
                event_store, tenant_id=tenant_id, event_type=event_type, end_ms=end_ms
            ):
                request_id = str((event.get("payload") or {}).get("request_id") or "").strip()
                if request_id:
                    ids.add(request_id)
        except Exception:
            continue
    return ids


def pricing_change_requests(event_store: Any, *, tenant_id: str = "default",
                            limit: int = 20, now_ms: int | None = None) -> list[dict[str, Any]]:
    """Last canonical or legacy pricing change requests and lifecycle status."""
    if event_store is None or not hasattr(event_store, "iter_events"):
        return []
    end_ms = resolve_now_ms(now_ms=now_ms)
    applied = _request_ids(event_store, tenant_id=str(tenant_id),
                           event_types=_APPLIED, end_ms=end_ms)
    rejected = _request_ids(event_store, tenant_id=str(tenant_id),
                            event_types=_REJECTED, end_ms=end_ms)
    requests: dict[str, dict[str, Any]] = {}
    try:
        for event_type in _REQUESTED:
            for event in iter_pricing_events(event_store, tenant_id=str(tenant_id),
                                             event_type=event_type, end_ms=end_ms):
                payload = event.get("payload") or {}
                request_id = str(payload.get("request_id") or "").strip()
                if not request_id or request_id in requests:
                    continue
                requests[request_id] = {
                    "request_id": request_id,
                    "plan_id": int(payload.get("plan_id") or 0),
                    "new_price": int(payload.get("new_price") or 0),
                    "product_id": str(payload.get("product_id") or "").strip(),
                    "business_id": str(payload.get("business_id") or "").strip(),
                    "suggested_pricing_version": str(payload.get("suggested_pricing_version") or "").strip(),
                    "reason": str(payload.get("reason") or "").strip(),
                    "requested_by": str(payload.get("requested_by") or event.get("user_id") or "").strip(),
                    "timestamp_ms": int(event.get("timestamp_ms") or 0),
                }
    except (TypeError, ValueError, AttributeError, RuntimeError):
        return []
    out: list[dict[str, Any]] = []
    for row in sorted(requests.values(), key=lambda r: r["timestamp_ms"], reverse=True):
        request_id = row["request_id"]
        row["status"] = "applied" if request_id in applied else (
            "rejected" if request_id in rejected else "pending"
        )
        out.append(row)
        if len(out) >= int(limit):
            break
    return out
