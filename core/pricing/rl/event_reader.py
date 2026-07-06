from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def iter_events(event_store: Any, *, tenant_id: str, start_ms: int, end_ms: int, event_type: str) -> Iterable[dict[str, Any]]:
    it = getattr(event_store, "iter_events", None)
    if not callable(it):
        return ()
    return it(tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type=str(event_type))


def collect_offer_shown(event_store: Any, *, tenant_id: str, offer_arm: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="offer_shown"):
        try:
            p = ev.get("payload") or {}
            arm = str(p.get("arm") or p.get("offer_arm") or "").strip()
            if arm != str(offer_arm):
                continue
            uid = str(ev.get("user_id") or "").strip()
            ts = int(ev.get("timestamp_ms") or 0)
            price = int(p.get("price_rub") or p.get("price") or 0)
            if not uid or ts <= 0 or price <= 0:
                continue
            seg = str(p.get("segment") or p.get("traffic_source") or p.get("utm_source") or p.get("channel") or "").strip()
            out.append({"event_id": str(ev.get("event_id") or "").strip(), "user_id": uid, "ts": ts, "amount": price, "segment": seg})
        except Exception:
            continue
    return out


def collect_offer_outcomes_index(event_store: Any, *, tenant_id: str, start_ms: int, end_ms: int) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="offer_outcome"):
        try:
            p = ev.get("payload") or {}
            sid = str(p.get("shown_event_id") or "").strip()
            if sid:
                out[sid] = bool(p.get("success"))
        except Exception:
            continue
    return out


def collect_trials_legacy(event_store: Any, *, tenant_id: str, offer_arm: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="tariff_selected"):
        try:
            p = ev.get("payload") or {}
            tariff = str(p.get("tariff") or "")
            if tariff != str(offer_arm):
                continue
            uid = str(ev.get("user_id") or "")
            amount = int(p.get("amount") or 0)
            ts = int(ev.get("timestamp_ms") or 0)
            if not uid or amount <= 0 or ts <= 0:
                continue
            seg = str(p.get("segment") or p.get("traffic_source") or p.get("utm_source") or p.get("channel") or "")
            trials.append({"user_id": uid, "amount": amount, "ts": ts, "segment": seg})
        except Exception:
            continue
    return trials


def collect_payments_index_legacy(event_store: Any, *, tenant_id: str, start_ms: int, end_ms: int) -> dict[str, list[int]]:
    payments_by_user: dict[str, list[int]] = {}
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="payment_captured"):
        try:
            uid = str(ev.get("user_id") or "")
            ts = int(ev.get("timestamp_ms") or 0)
            payload = ev.get("payload") or {}
            ok = True
            if isinstance(payload, dict) and "ok" in payload:
                ok = bool(payload.get("ok"))
            if not uid or ts <= 0 or not ok:
                continue
            payments_by_user.setdefault(uid, []).append(ts)
        except Exception:
            continue
    for uid in list(payments_by_user.keys()):
        payments_by_user[uid].sort()
    return payments_by_user
