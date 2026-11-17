from __future__ import annotations

from typing import Any

from core.telemetry.behavior_read_model import behavior_snapshot
from interfaces.telegram.read_models.components.pricing import load_pricing_suggestions
from interfaces.telegram.read_models.components.profile import load_user_profile
from runtime.platform.config.feature_flags import FeatureFlags


def load_user_bundle(*, event_store: Any, tenant_id: str, user_id: str, event_warning: Any,
                     product_id: str | None = None) -> dict[str, Any]:
    try:
        from core.entitlements.read_model import compute_entitlements
        entitlements = compute_entitlements(event_store=event_store, tenant_id=str(tenant_id), user_id=str(user_id),
                                            product_id=product_id)
    except Exception:
        entitlements = {"full_access": False, "reason": "read_error"}

    try:
        from core.payments.read_model import latest_payment_status
        payments = latest_payment_status(event_store=event_store, tenant_id=str(tenant_id), user_id=str(user_id),
                                         product_id=product_id)
    except Exception:
        payments = {"status": "unknown", "reason": "read_error"}

    realtime_state = {}
    if FeatureFlags.CONTINUOUS_STATE:
        try:
            if hasattr(event_store, "get_user_state"):
                realtime_state = event_store.get_user_state(tenant_id=tenant_id, user_id=str(user_id))
        except Exception:
            realtime_state = {}

    pricing_suggestions = load_pricing_suggestions(event_store, tenant_id=str(tenant_id))
    settings, city, tariff, moods = load_user_profile(event_store, tenant_id=str(tenant_id), user_id=str(user_id))

    try:
        from core.admin.roles_read_model import perms_for_user, roles_for_user
        roles = sorted(list(roles_for_user(event_store, tenant_id=str(tenant_id), user_id=str(user_id))))
        perms = sorted(list(perms_for_user(event_store, tenant_id=str(tenant_id), user_id=str(user_id))))
    except Exception:
        roles, perms = [], []

    try:
        from core.admin.marketing_read_model import marketing_variants
        marketing_variants_payload = marketing_variants(event_store, tenant_id=str(tenant_id))
    except Exception:
        marketing_variants_payload = {}

    marketing_bandit = {
        "tariffs_viewed": {
            "a": {"alpha": 1.0, "beta": 1.0},
            "b": {"alpha": 1.0, "beta": 1.0},
        }
    }
    if FeatureFlags.MARKETING_BANDIT:
        try:
            from core.admin.marketing_bandit_read_model import marketing_bandit_stats
            marketing_bandit = marketing_bandit_stats(event_store, tenant_id=str(tenant_id), step_key="tariffs_viewed", window_days=30)
        except Exception as exc:
            marketing_bandit = {
                "tariffs_viewed": {
                    "a": {"alpha": 1.0, "beta": 1.0},
                    "b": {"alpha": 1.0, "beta": 1.0},
                }
            }
            event_warning(reason="marketing_bandit_stats_failed", error=exc.__class__.__name__)

    try:
        behavior = behavior_snapshot(event_store, tenant_id=tenant_id, user_id=str(user_id))
    except Exception:
        behavior = {}

    try:
        from core.autopilot.read_model import recent_autopilot_actions, today_business_metrics
        autopilot_dashboard = {
            "today": today_business_metrics(event_store, tenant_id=str(tenant_id)),
            "actions_7d": recent_autopilot_actions(event_store, tenant_id=str(tenant_id), days=7),
        }
    except Exception:
        autopilot_dashboard = {}
    try:  # AI-director KPI: the same canonical today growth ledger, never an empty stand-in
        from core.growth.today_ledger import build_today_kpi
        kpi = build_today_kpi(event_store, tenant_id=str(tenant_id))
        autopilot_dashboard["growth"] = {"leads": int(kpi.leads), "spend_minor": int(kpi.spend_minor),
                                         "revenue_minor": int(kpi.revenue_minor), "profit_minor": int(kpi.profit_minor)}
    except Exception:
        pass

    return {
        "entitlements": entitlements,
        "payments": payments,
        "realtime_state": realtime_state,
        "pricing_suggestions": pricing_suggestions,
        "settings": settings,
        "city": city,
        "selected_tariff": tariff,
        "mood_last": moods,
        "roles": roles,
        "perms": perms,
        "marketing_variants": marketing_variants_payload,
        "marketing_bandit": marketing_bandit,
        "behavior": behavior,
        "autopilot_dashboard": autopilot_dashboard,
    }


_HYDRATED_USER_KEYS = (
    "settings", "city", "selected_tariff", "mood_last", "roles", "perms", "pricing_suggestions",
    "realtime_state", "autopilot_dashboard", "marketing_variants", "marketing_bandit",
)


def hydrate_world_state_user(state: Any, *, event_store: Any) -> Any:
    """Authoritative tenant/product-scoped user projection for platform bot.

    Never promote an aggregate payment or entitlement to product access.
    """
    from dataclasses import replace

    tenant_id = str(getattr(state, "tenant_id", "") or "")
    user_id = str(getattr(state, "user_id", "") or "")
    product = getattr(state, "product", None)
    product_id = str((product if isinstance(product, dict) else {}).get("product_id") or "").strip()
    if not tenant_id or not user_id or event_store is None:
        return state
    try:
        bundle = load_user_bundle(
            event_store=event_store, tenant_id=tenant_id, user_id=user_id,
            event_warning=lambda reason, error: None, product_id=product_id or None,
        )
    except Exception:
        return state
    user = {**dict(getattr(state, "user", None) or {}),
            **{key: bundle[key] for key in _HYDRATED_USER_KEYS}}
    try:
        from interfaces.telegram.read_models.admin_access import is_superadmin, load_admin_metrics

        if is_superadmin(user_id) or "admin" in {str(role) for role in bundle["roles"]}:
            user["admin_metrics"] = load_admin_metrics(event_store=event_store, tenant_id=tenant_id)
    except Exception:
        user.pop("admin_metrics", None)
    payments = bundle["payments"] if product_id else {"status": "none", "reason": "unscoped"}
    entitlements = bundle["entitlements"] if product_id else {"full_access": False, "reason": "unscoped"}
    economy = {**dict(getattr(state, "economy", None) or {}),
               "payments": payments, "entitlements": entitlements}
    return replace(state, user=user, economy=economy)
