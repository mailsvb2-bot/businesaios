from __future__ import annotations

from typing import Any, Dict

from runtime.platform.config.feature_flags import FeatureFlags


def load_admin_metrics(event_store: Any, *, tenant_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        from core.admin.read_model import users_today, funnel_counts, demo_summary, retention_brief, health_brief, pricing_change_requests, latency_brief
        try:
            out["users_today"] = users_today(event_store, tenant_id=str(tenant_id))
        except Exception:
            out["users_today"] = 0
        try:
            evs = [
                "tariffs_viewed",
                "tariff_selected",
                "payment_created",
                "payment_captured",
                "access_granted",
                "audio_sent",
            ]
            out["funnel"] = funnel_counts(event_store, evs, tenant_id=str(tenant_id))
        except Exception:
            out["funnel"] = {}
        try:
            out["demo"] = demo_summary(event_store, tenant_id=str(tenant_id))
        except Exception:
            out["demo"] = {"sent_work": 0, "sent_home": 0, "users": 0}
        try:
            out["retention"] = retention_brief(event_store, tenant_id=str(tenant_id))
        except Exception:
            out["retention"] = {"users": 0, "active_2d": 0}
        try:
            out["health"] = health_brief(event_store, tenant_id=str(tenant_id))
        except Exception:
            out["health"] = {"events": 0}
        try:
            if FeatureFlags.LATENCY_AI:
                out["latency"] = latency_brief(event_store, tenant_id=str(tenant_id), days=7, limit=10)
        except Exception:
            out["latency"] = {"top_slowest": [], "window_days": 7, "samples": 0}
        try:
            out["pricing_requests"] = pricing_change_requests(event_store, tenant_id=str(tenant_id), limit=20)
        except Exception:
            out["pricing_requests"] = []
    except Exception:
        out = {"users_today": 0}
    return out
