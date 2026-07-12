"""User read-models (event-sourced).

These helpers are PURE and deterministic. They do not perform IO themselves;
they only consume the provided event_store adapter.
"""

from __future__ import annotations

from typing import Any

from core.events.read_model_support import (
    best_effort_iter_events,
    best_effort_latest_event,
    best_effort_latest_events,
)
from core.read_model.cache import global_cache, watermark_for


def _iter_user_events(
    event_store: Any,
    *,
    tenant_id: str = "default",
    user_id: str,
    types: set[str] | None = None,
):
    if event_store is None:
        return []
    event_types = tuple(sorted(str(item) for item in types)) if types else ()
    events = best_effort_iter_events(
        event_store=event_store,
        where="core/users/read_model._iter_user_events",
        tenant_id=str(tenant_id),
        event_types=event_types,
        start_ms=0,
        end_ms=None,
        user_id=str(user_id),
    )
    return [ev for ev in events if types is None or str(ev.get("event_type") or ev.get("type")) in types]


def user_settings(event_store: Any, *, tenant_id: str = "default", user_id: str) -> dict[str, Any]:
    tenant = str(tenant_id)
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=tenant, user_id=uid, event_types=("user_setting_set",))

    def _compute() -> dict[str, Any]:
        settings: dict[str, Any] = {}
        evs = best_effort_latest_events(
            event_store=event_store,
            where="core/users/read_model.user_settings",
            tenant_id=tenant,
            user_id=uid,
            event_types=("user_setting_set",),
            legacy_event_type="user_setting_set",
            limit=200,
        )
        if evs:
            seen: set[str] = set()
            for ev in evs:
                payload = ev.get("payload") or {}
                key = payload.get("key")
                if not key:
                    continue
                key_text = str(key)
                if key_text in seen:
                    continue
                seen.add(key_text)
                settings[key_text] = payload.get("value")
            return settings

        for ev in _iter_user_events(
            event_store,
            tenant_id=tenant,
            user_id=uid,
            types={"user_setting_set"},
        ):
            payload = ev.get("payload") or {}
            key = payload.get("key")
            if not key:
                continue
            settings[str(key)] = payload.get("value")
        return settings

    return global_cache().get(
        key=("user_settings", tenant, uid),
        compute=_compute,
        watermark_ms=wm,
    )


def user_city(event_store: Any, *, tenant_id: str = "default", user_id: str, default: str = "") -> str:
    settings = user_settings(event_store, tenant_id=str(tenant_id), user_id=user_id)
    city = settings.get("city")
    if isinstance(city, str) and city.strip():
        return city.strip()[:128]
    return str(default or "")


def selected_tariff(event_store: Any, *, tenant_id: str = "default", user_id: str) -> dict[str, Any] | None:
    tenant = str(tenant_id)
    uid = str(user_id)
    wm = watermark_for(event_store, tenant_id=tenant, user_id=uid, event_types=("tariff_selected",))

    def _compute() -> dict[str, Any] | None:
        last = best_effort_latest_event(
            event_store=event_store,
            where="core/users/read_model.selected_tariff",
            tenant_id=tenant,
            user_id=uid,
            event_types=("tariff_selected",),
            legacy_event_type="tariff_selected",
        )
        if last is None:
            for ev in _iter_user_events(
                event_store,
                tenant_id=tenant,
                user_id=uid,
                types={"tariff_selected"},
            ):
                last = ev
        if not last:
            return None
        payload = last.get("payload") or {}
        if not isinstance(payload, dict):
            return None
        return {
            "tariff": payload.get("tariff"),
            "period": payload.get("period"),
            "days": payload.get("days"),
            "amount": payload.get("amount"),
            "plan_id": payload.get("plan_id"),
            "title": payload.get("title"),
            "expected_price": payload.get("expected_price"),
            "ts": last.get("timestamp_ms"),
        }

    return global_cache().get(
        key=("selected_tariff", tenant, uid),
        compute=_compute,
        watermark_ms=wm,
    )


def selected_product(
    event_store: Any,
    *,
    tenant_id: str = "default",
    user_id: str,
) -> dict[str, Any] | None:
    """Return the last selected product context for one tenant/user boundary."""

    tenant = str(tenant_id)
    uid = str(user_id)
    event_type = "product_selected@v1"
    wm = watermark_for(
        event_store,
        tenant_id=tenant,
        user_id=uid,
        event_types=(event_type,),
    )

    def _compute() -> dict[str, Any] | None:
        last = best_effort_latest_event(
            event_store=event_store,
            where="core/users/read_model.selected_product",
            tenant_id=tenant,
            user_id=uid,
            event_types=(event_type,),
            legacy_event_type=event_type,
        )
        if last is None:
            for ev in _iter_user_events(
                event_store,
                tenant_id=tenant,
                user_id=uid,
                types={event_type},
            ):
                last = ev
        if not last:
            return None
        payload = last.get("payload") or {}
        if not isinstance(payload, dict):
            return None
        result: dict[str, Any] = {**payload}
        result["ts"] = last.get("timestamp_ms")
        return result

    return global_cache().get(
        key=("selected_product", tenant, uid),
        compute=_compute,
        watermark_ms=wm,
    )
