from __future__ import annotations

from typing import Any

from runtime.platform.config.feature_flags import FeatureFlags
from core.telemetry.behavior_read_model import behavior_snapshot
from interfaces.telegram.read_models.components.pricing import load_pricing_suggestions
from interfaces.telegram.read_models.components.profile import load_user_profile


def load_user_bundle(*, event_store: Any, tenant_id: str, user_id: str, event_warning: Any) -> dict[str, Any]:
    try:
        from core.entitlements.read_model import compute_entitlements
        entitlements = compute_entitlements(event_store=event_store, tenant_id=str(tenant_id), user_id=str(user_id))
    except Exception:
        entitlements = {"full_access": False, "reason": "read_error"}

    try:
        from core.payments.read_model import latest_payment_status
        payments = latest_payment_status(event_store=event_store, tenant_id=str(tenant_id), user_id=str(user_id))
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
        from core.admin.roles_read_model import roles_for_user, perms_for_user
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
        from core.autopilot.read_model import today_business_metrics, recent_autopilot_actions
        autopilot_dashboard = {
            "today": today_business_metrics(event_store, tenant_id=str(tenant_id)),
            "actions_7d": recent_autopilot_actions(event_store, tenant_id=str(tenant_id), days=7),
        }
    except Exception:
        autopilot_dashboard = {}

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
