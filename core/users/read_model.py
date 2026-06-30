"""User read-models (event-sourced).

These helpers are PURE and deterministic. They do not perform IO themselves;
they only consume the provided event_store adapter.

Why:
- Keep the "single brain" rule: policies do not query databases directly.
- TelegramRunner can enrich WorldState.user from these read models.
"""

from __future__ import annotations

from typing import Any
from core.events.read_model_support import (
    best_effort_iter_events,
    best_effort_latest_event,
    best_effort_latest_events,
)
from core.read_model.cache import global_cache, watermark_for

def _iter_user_events(event_store: Any, *, tenant_id: str = "default", user_id: str, types: set[str] | None = None):
    if event_store is None:
        return []
    event_types = tuple(sorted(str(item) for item in types)) if types else ()
    events = best_effort_iter_events(
        event_store=event_store,
        where='core/users/read_model._iter_user_events',
        tenant_id=str(tenant_id),
        event_types=event_types,
        start_ms=0,
        end_ms=None,
        user_id=str(user_id),
    )
    return [ev for ev in events if types is None or str(ev.get("event_type") or ev.get("type")) in types]


def user_settings(event_store: Any, *, tenant_id: str = "default", user_id: str) -> dict[str, Any]:
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=str(tenant_id), user_id=uid, event_types=("user_setting_set",))

    def _compute() -> dict[str, Any]:
        settings: dict[str, Any] = {}
        evs = best_effort_latest_events(
            event_store=event_store,
            where='core/users/read_model.user_settings',
            tenant_id=str(tenant_id),
            user_id=uid,
            event_types=("user_setting_set",),
            legacy_event_type="user_setting_set",
            limit=200,
        )
        if evs:
            seen = set()
            for ev in evs:
                p = ev.get("payload") or {}
                k = p.get("key")
                if not k:
                    continue
                ks = str(k)
                if ks in seen:
                    continue
                seen.add(ks)
                settings[ks] = p.get("value")
            return settings

        for ev in _iter_user_events(event_store, tenant_id=str(tenant_id), user_id=uid, types={"user_setting_set"}):
            p = ev.get("payload") or {}
            k = p.get("key")
            if not k:
                continue
            settings[str(k)] = p.get("value")
        return settings

    return global_cache().get(key=("user_settings", uid), compute=_compute, watermark_ms=wm)


def user_city(event_store: Any, *, tenant_id: str = "default", user_id: str, default: str = "Amsterdam") -> str:
    s = user_settings(event_store, tenant_id=str(tenant_id), user_id=user_id)
    city = s.get("city")
    if isinstance(city, str) and city.strip():
        return city.strip()[:128]
    return str(default)


def selected_tariff(event_store: Any, *, tenant_id: str = "default", user_id: str) -> dict[str, Any] | None:
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=str(tenant_id), user_id=uid, event_types=("tariff_selected",))

    def _compute() -> dict[str, Any] | None:
        last = best_effort_latest_event(
            event_store=event_store,
            where='core/users/read_model.selected_tariff',
            tenant_id=str(tenant_id),
            user_id=uid,
            event_types=("tariff_selected",),
            legacy_event_type="tariff_selected",
        )
        if last is None:
            for ev in _iter_user_events(event_store, tenant_id=str(tenant_id), user_id=uid, types={"tariff_selected"}):
                last = ev
        if not last:
            return None
        p = last.get("payload") or {}
        if not isinstance(p, dict):
            return None
        return {
            "tariff": p.get("tariff"),
            "period": p.get("period"),
            "days": p.get("days"),
            "amount": p.get("amount"),
            "plan_id": p.get("plan_id"),
            "title": p.get("title"),
            "expected_price": p.get("expected_price"),
            "ts": last.get("timestamp_ms"),
        }

    return global_cache().get(key=("selected_tariff", uid), compute=_compute, watermark_ms=wm)


def mood_last(event_store: Any, *, tenant_id: str = "default", user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=str(tenant_id), user_id=uid, event_types=("mood_logged",))

    def _compute() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        evs = list(reversed(best_effort_latest_events(
            event_store=event_store,
            where='core/users/read_model.mood_last',
            tenant_id=str(tenant_id),
            user_id=uid,
            event_types=("mood_logged",),
            legacy_event_type="mood_logged",
            limit=int(limit),
        )))
        if not evs:
            evs = _iter_user_events(event_store, user_id=uid, types={"mood_logged"})

        for ev in evs:
            p = ev.get("payload") or {}
            if not isinstance(p, dict):
                continue
            items.append({"ts": ev.get("timestamp_ms"), "score": p.get("score"), "note": p.get("note")})
        return items[-int(limit) :]

    return global_cache().get(key=("mood_last", uid, int(limit)), compute=_compute, watermark_ms=wm)



def selected_product(event_store: Any, *, user_id: str) -> dict[str, Any] | None:
    """Return last selected product context for user (persisted via events).

    Event type: product_selected@v1
    Payload may include: product_config, product_id, domain, modules
    """
    uid = str(user_id)
    wm = watermark_for(event_store, user_id=uid, event_types=("product_selected@v1",))

    def _compute() -> dict[str, Any] | None:
        last = best_effort_latest_event(
            event_store=event_store,
            where='core/users/read_model.selected_product',
            tenant_id="default",
            user_id=uid,
            event_types=("product_selected@v1",),
            legacy_event_type="product_selected@v1",
        )
        if last is None:
            for ev in _iter_user_events(event_store, user_id=uid, types={"product_selected@v1"}):
                last = ev
        if not last:
            return None
        p = last.get("payload") or {}
        if not isinstance(p, dict):
            return None
        out: dict[str, Any] = {**p}
        out["ts"] = last.get("timestamp_ms")
        return out

    return global_cache().get(key=("selected_product", uid), compute=_compute, watermark_ms=wm)
