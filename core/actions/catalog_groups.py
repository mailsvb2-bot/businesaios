from __future__ import annotations

from core.actions.names import ACTION_ADS_APPLY_EXECUTE_V1, ACTION_AI_CEO_PLAN_V1
from core.ai.schema_registry import DecisionSchema

from .catalog_entry import CatalogEntry

FieldType = type | tuple[type, ...]


def _entry(
    action: str,
    version: int,
    *,
    required: set[str],
    optional: set[str],
    field_types: dict[str, FieldType],
) -> CatalogEntry:
    return CatalogEntry(
        action=action,
        version=version,
        schema=DecisionSchema(
            required=set(required),
            optional=set(optional),
            field_types=dict(field_types),
        ),
    )


def base_catalog() -> dict[str, CatalogEntry]:
    return {
        "noop@v1": _entry("noop@v1", 1, required=set(), optional=set(), field_types={}),
        "poll_telegram_updates@v1": _entry(
            "poll_telegram_updates@v1",
            1,
            required=set(),
            optional={"offset", "timeout_s", "limit"},
            field_types={"offset": int, "timeout_s": int, "limit": int},
        ),
        "send_message@v1": _entry(
            "send_message@v1",
            1,
            required={"tenant_id", "user_id", "text"},
            optional={"chat_id", "reply_markup", "callback_query_id", "track_event_type", "track_payload", "kind", "priority", "critical", "best_effort", "channel", "channel_policy"},
            field_types={"tenant_id": str, "user_id": str, "text": str, "chat_id": int, "reply_markup": dict, "callback_query_id": str, "track_event_type": str, "track_payload": dict, "kind": str, "priority": str, "critical": bool, "best_effort": bool, "channel": str, "channel_policy": dict},
        ),
        "track_event@v1": _entry("track_event@v1", 1, required={"user_id", "event_type"}, optional={"payload", "source"}, field_types={"user_id": str, "event_type": str, "payload": dict, "source": str}),
        "answer_callback@v1": _entry("answer_callback@v1", 1, required={"callback_query_id"}, optional={"text", "show_alert"}, field_types={"callback_query_id": str, "text": str, "show_alert": bool}),
        "emit_event@v1": _entry("emit_event@v1", 1, required={"user_id", "event_type"}, optional={"payload", "source"}, field_types={"user_id": str, "event_type": str, "payload": dict, "source": str}),
        "enqueue_evolution_job@v1": _entry("enqueue_evolution_job@v1", 1, required={"tenant_id", "user_id", "job_kind"}, optional={"payload"}, field_types={"tenant_id": str, "user_id": str, "job_kind": str, "payload": dict}),
        "execute_plan@v1": _entry("execute_plan@v1", 1, required={"user_id", "steps"}, optional=set(), field_types={"user_id": str, "steps": list}),
    }


def behavior_graph_catalog() -> dict[str, CatalogEntry]:
    return {
        "behavior_graph_build@v1": _entry("behavior_graph_build@v1", 1, required=set(), optional={"tenant_id", "user_id", "scope", "start_ms", "end_ms", "max_events", "enable_sequence_edges"}, field_types={"tenant_id": str, "user_id": str, "scope": str, "start_ms": int, "end_ms": int, "max_events": int, "enable_sequence_edges": bool}),
        "behavior_graph_neighbors@v1": _entry("behavior_graph_neighbors@v1", 1, required={"node_id"}, optional={"tenant_id", "user_id", "scope", "direction", "limit", "edge_type"}, field_types={"tenant_id": str, "user_id": str, "scope": str, "node_id": str, "direction": str, "limit": int, "edge_type": str}),
        "behavior_graph_path@v1": _entry("behavior_graph_path@v1", 1, required={"src", "dst"}, optional={"tenant_id", "user_id", "scope", "max_hops"}, field_types={"tenant_id": str, "user_id": str, "scope": str, "src": str, "dst": str, "max_hops": int}),
        "behavior_graph_node@v1": _entry("behavior_graph_node@v1", 1, required={"node_id"}, optional={"tenant_id", "user_id", "scope"}, field_types={"tenant_id": str, "user_id": str, "scope": str, "node_id": str}),
        "behavior_graph_reset@v1": _entry("behavior_graph_reset@v1", 1, required=set(), optional={"tenant_id", "user_id", "scope"}, field_types={"tenant_id": str, "user_id": str, "scope": str}),
    }


def ads_catalog() -> dict[str, CatalogEntry]:
    return {
        ACTION_ADS_APPLY_EXECUTE_V1: _entry(
            ACTION_ADS_APPLY_EXECUTE_V1,
            1,
            required={"tenant_id", "user_id", "idempotency_key"},
            optional={"plan", "commands", "steps", "gate_settings", "dry_run", "rollback_on_fail", "reason", "callback_query_id"},
            field_types={"tenant_id": str, "user_id": str, "idempotency_key": str, "plan": (dict, list), "commands": list, "steps": list, "gate_settings": dict, "dry_run": bool, "rollback_on_fail": bool, "reason": str, "callback_query_id": str},
        ),
        "ads_rl_suggest@v1": _entry("ads_rl_suggest@v1", 1, required={"tenant_id", "user_id"}, optional={"current_daily_budget_minor"}, field_types={"tenant_id": str, "user_id": str, "current_daily_budget_minor": int}),
        "ads_rl_train_tick@v1": _entry(
            "ads_rl_train_tick@v1",
            1,
            required={"tenant_id", "user_id"},
            optional={"decision_ids", "lookback_days", "min_matured", "min_transitions"},
            field_types={"tenant_id": str, "user_id": str, "decision_ids": list, "lookback_days": int, "min_matured": int, "min_transitions": int},
        ),
        "ads_autopilot_tick@v1": _entry(
            "ads_autopilot_tick@v1",
            1,
            required={"tenant_id", "user_id"},
            optional={"objective", "offer", "audience", "channels", "constraints", "max_daily_budget_minor", "max_total_budget_minor", "currency", "allowed_platforms", "callback_query_id"},
            field_types={"tenant_id": str, "user_id": str, "objective": (str, dict), "offer": dict, "audience": dict, "channels": list, "constraints": dict, "max_daily_budget_minor": int, "max_total_budget_minor": int, "currency": str, "allowed_platforms": list, "callback_query_id": str},
        ),
    }


def payments_catalog() -> dict[str, CatalogEntry]:
    payment_optional = {"provider", "metadata", "expected_amount", "pricing_version"}
    payment_types: dict[str, FieldType] = {"tenant_id": str, "product_id": str, "order_id": str, "user_id": str, "amount": int, "currency": str, "provider": str, "metadata": dict, "expected_amount": int, "pricing_version": str}
    payment_required = {"tenant_id", "product_id", "order_id", "user_id", "amount", "currency"}
    return {
        "capture_payment@v1": _entry("capture_payment@v1", 1, required=payment_required, optional=payment_optional, field_types=payment_types),
        "create_payment_and_send_link@v1": _entry("create_payment_and_send_link@v1", 1, required=payment_required, optional=payment_optional, field_types=payment_types),
        "reconcile_payments@v1": _entry("reconcile_payments@v1", 1, required=set(), optional={"window_min"}, field_types={"window_min": int}),
        "reconcile_payment@v1": _entry("reconcile_payment@v1", 1, required={"external_id"}, optional={"notification_id", "event", "user_id"}, field_types={"external_id": str, "notification_id": str, "event": str, "user_id": str}),
        "grant_access@v1": _entry("grant_access@v1", 1, required={"tenant_id", "product_id", "user_id"}, optional={"grant_key", "full_access", "notify_text", "notify_reply_markup", "track_event_type", "track_payload"}, field_types={"tenant_id": str, "product_id": str, "user_id": str, "grant_key": str, "full_access": bool, "notify_text": str, "notify_reply_markup": dict, "track_event_type": str, "track_payload": dict}),
        "select_tariff@v1": _entry("select_tariff@v1", 1, required={"tenant_id", "product_id", "user_id", "tariff", "days", "period", "amount"}, optional={"plan_id", "title", "expected_price", "notify_text", "notify_reply_markup", "segment", "traffic_source", "utm_source", "channel"}, field_types={"tenant_id": str, "product_id": str, "user_id": str, "tariff": str, "days": int, "period": str, "amount": int, "plan_id": int, "title": str, "expected_price": int, "notify_text": str, "notify_reply_markup": dict, "segment": str, "traffic_source": str, "utm_source": str, "channel": str}),
    }


def growth_catalog() -> dict[str, CatalogEntry]:
    return {
        "send_marketing_offer@v1": _entry("send_marketing_offer@v1", 1, required={"tenant_id", "user_id", "offer"}, optional={"locale", "channel", "features", "last_user_text", "fallback_text", "reply_markup", "callback_query_id", "track_event_type", "track_payload", "priority", "critical", "best_effort", "channel_policy"}, field_types={"tenant_id": str, "user_id": str, "locale": str, "channel": str, "offer": dict, "features": dict, "last_user_text": str, "fallback_text": str, "reply_markup": dict, "callback_query_id": str, "track_event_type": str, "track_payload": dict, "priority": str, "critical": bool, "best_effort": bool, "channel_policy": dict}),
        "one_click_value@v1": _entry("one_click_value@v1", 1, required={"tenant_id", "user_id", "locale", "channel", "offer"}, optional={"features", "last_user_text", "reply_markup", "callback_query_id", "track_event_type", "track_payload", "fallback_text", "channel_policy"}, field_types={"tenant_id": str, "user_id": str, "locale": str, "channel": str, "offer": dict, "features": dict, "last_user_text": str, "reply_markup": dict, "callback_query_id": str, "track_event_type": str, "track_payload": dict, "fallback_text": str, "channel_policy": dict}),
        "send_audio@v1": _entry("send_audio@v1", 1, required={"tenant_id", "user_id", "path"}, optional={"kind", "caption", "callback_query_id", "channel"}, field_types={"tenant_id": str, "user_id": str, "path": str, "kind": str, "caption": str, "callback_query_id": str, "channel": str}),
        "send_weather@v1": _entry("send_weather@v1", 1, required={"tenant_id", "user_id", "city"}, optional=set(), field_types={"tenant_id": str, "user_id": str, "city": str}),
        ACTION_AI_CEO_PLAN_V1: _entry(ACTION_AI_CEO_PLAN_V1, 1, required={"tenant_id", "user_id"}, optional={"objective", "horizon"}, field_types={"tenant_id": str, "user_id": str, "objective": str, "horizon": str}),
        "pricing_select@v1": _entry("pricing_select@v1", 1, required={"tenant_id", "product_id", "user_id"}, optional={"candidates", "evidence"}, field_types={"tenant_id": str, "product_id": str, "user_id": str, "candidates": list, "evidence": dict}),
        "reward_observe@v1": _entry("reward_observe@v1", 1, required={"tenant_id", "user_id"}, optional={"metrics", "channel", "channel_policy"}, field_types={"tenant_id": str, "user_id": str, "metrics": dict, "channel": str, "channel_policy": dict}),
        "growth_propose@v1": _entry("growth_propose@v1", 1, required={"tenant_id", "user_id"}, optional={"objective", "signals", "channel", "channel_policy"}, field_types={"tenant_id": str, "user_id": str, "objective": str, "signals": dict, "channel": str, "channel_policy": dict}),
        "profit_sprint_onboarding_start@v1": _entry("profit_sprint_onboarding_start@v1", 1, required={"tenant_id", "user_id"}, optional={"product_id", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "product_id": str, "callback_query_id": str}),
        "profit_sprint_onboarding_text@v1": _entry("profit_sprint_onboarding_text@v1", 1, required={"tenant_id", "user_id"}, optional={"product_id", "text", "value", "answer", "step", "field", "question", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "product_id": str, "text": str, "value": str, "answer": str, "step": str, "field": str, "question": str, "callback_query_id": str}),
        "profit_sprint_onboarding_lead_source@v1": _entry("profit_sprint_onboarding_lead_source@v1", 1, required={"tenant_id", "user_id"}, optional={"product_id", "lead_source", "value", "source", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "product_id": str, "lead_source": str, "value": str, "source": str, "callback_query_id": str}),
        "growth_strategy_generate@v1": _entry("growth_strategy_generate@v1", 1, required={"tenant_id", "user_id"}, optional={"goal", "n", "model", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "goal": dict, "n": int, "model": str, "callback_query_id": str}),
        "growth_strategy_backlog@v1": _entry("growth_strategy_backlog@v1", 1, required={"tenant_id", "user_id"}, optional={"limit", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "limit": int, "callback_query_id": str}),
        "growth_strategy_accept@v1": _entry("growth_strategy_accept@v1", 1, required={"tenant_id", "user_id", "hypothesis_id"}, optional={"callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "hypothesis_id": str, "callback_query_id": str}),
        "growth_strategy_reject@v1": _entry("growth_strategy_reject@v1", 1, required={"tenant_id", "user_id", "hypothesis_id"}, optional={"callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "hypothesis_id": str, "callback_query_id": str}),
    }


def user_state_catalog() -> dict[str, CatalogEntry]:
    return {
        "set_user_setting@v1": _entry("set_user_setting@v1", 1, required={"tenant_id", "user_id", "key"}, optional={"value", "notify_text", "notify_reply_markup", "callback_query_id"}, field_types={"tenant_id": str, "user_id": str, "key": str, "value": object, "notify_text": str, "notify_reply_markup": dict, "callback_query_id": str}),
        "log_mood@v1": _entry("log_mood@v1", 1, required={"tenant_id", "user_id", "score"}, optional={"note", "notify_text", "notify_reply_markup", "callback_query_id", "channel", "channel_policy"}, field_types={"tenant_id": str, "user_id": str, "score": int, "note": str, "notify_text": str, "notify_reply_markup": dict, "callback_query_id": str, "channel": str, "channel_policy": dict}),
    }


def governance_catalog() -> dict[str, CatalogEntry]:
    return {
        "deploy_policy@v1": _entry("deploy_policy@v1", 1, required={"tenant_id", "candidate_policy_id", "rollout_pct"}, optional=set(), field_types={"tenant_id": str, "candidate_policy_id": str, "rollout_pct": int}),
        "rollback_policy@v1": _entry("rollback_policy@v1", 1, required={"tenant_id", "reason"}, optional=set(), field_types={"tenant_id": str, "reason": str}),
        "admin_user_card@v1": _entry("admin_user_card@v1", 1, required={"tenant_id", "admin_id", "target_user_id"}, optional={"product_id"}, field_types={"tenant_id": str, "product_id": str, "admin_id": str, "target_user_id": str}),
        "admin_set_role@v1": _entry("admin_set_role@v1", 1, required={"tenant_id", "admin_id", "target_user_id", "role", "enabled"}, optional={"notify_text", "notify_reply_markup", "callback_query_id"}, field_types={"tenant_id": str, "admin_id": str, "target_user_id": str, "role": str, "enabled": bool, "notify_text": str, "notify_reply_markup": dict, "callback_query_id": str}),
        "admin_set_perm@v1": _entry("admin_set_perm@v1", 1, required={"tenant_id", "admin_id", "target_user_id", "perm", "enabled"}, optional={"notify_text", "notify_reply_markup", "callback_query_id"}, field_types={"tenant_id": str, "admin_id": str, "target_user_id": str, "perm": str, "enabled": bool, "notify_text": str, "notify_reply_markup": dict, "callback_query_id": str}),
        "set_marketing_copy@v1": _entry("set_marketing_copy@v1", 1, required={"tenant_id", "admin_id", "step_key", "variant_a", "variant_b"}, optional={"notify_text", "notify_reply_markup", "callback_query_id"}, field_types={"tenant_id": str, "admin_id": str, "step_key": str, "variant_a": str, "variant_b": str, "notify_text": str, "notify_reply_markup": dict, "callback_query_id": str}),
        "apply_pricing_change@v1": _entry("apply_pricing_change@v1", 1, required={"tenant_id", "product_id", "admin_id", "new_price", "pricing_version", "request_id"}, optional={"environment", "offer_id", "plan_id", "reason"}, field_types={"tenant_id": str, "product_id": str, "admin_id": str, "environment": str, "offer_id": str, "plan_id": int, "new_price": int, "pricing_version": str, "request_id": str, "reason": str}),
        "request_pricing_change@v1": _entry("request_pricing_change@v1", 1, required={"tenant_id", "product_id", "admin_id", "new_price", "request_id"}, optional={"environment", "offer_id", "plan_id", "suggested_pricing_version", "reason"}, field_types={"tenant_id": str, "product_id": str, "admin_id": str, "environment": str, "offer_id": str, "plan_id": int, "new_price": int, "request_id": str, "suggested_pricing_version": str, "reason": str}),
        "reject_pricing_change@v1": _entry("reject_pricing_change@v1", 1, required={"tenant_id", "admin_id", "request_id"}, optional={"product_id", "reason"}, field_types={"tenant_id": str, "product_id": str, "admin_id": str, "request_id": str, "reason": str}),
        "suggest_offer_patch@v1": _entry("suggest_offer_patch@v1", 1, required={"tenant_id", "product", "env", "offer_id", "action"}, optional={"notify_user_id", "callback_query_id"}, field_types={"tenant_id": str, "product": str, "env": str, "offer_id": str, "action": str, "notify_user_id": str, "callback_query_id": str}),
        "apply_offer_patch@v1": _entry("apply_offer_patch@v1", 1, required={"tenant_id", "product", "env", "offer_id"}, optional={"patch", "mode", "notify_user_id", "callback_query_id"}, field_types={"tenant_id": str, "product": str, "env": str, "offer_id": str, "patch": dict, "mode": str, "notify_user_id": str, "callback_query_id": str}),
    }


def build_catalog_groups() -> tuple[dict[str, CatalogEntry], ...]:
    return (
        base_catalog(),
        behavior_graph_catalog(),
        ads_catalog(),
        payments_catalog(),
        growth_catalog(),
        user_state_catalog(),
        governance_catalog(),
    )


CANON_ACTION_CATALOG_GROUPS = True


def telegram_actions() -> dict[str, CatalogEntry]:
    return dict(base_catalog())


def payments_actions() -> dict[str, CatalogEntry]:
    return dict(payments_catalog())


def growth_actions() -> dict[str, CatalogEntry]:
    return dict(growth_catalog())


def ads_actions() -> dict[str, CatalogEntry]:
    return dict(ads_catalog())


def admin_actions() -> dict[str, CatalogEntry]:
    return dict(governance_catalog())


__all__ = [
    "base_catalog",
    "behavior_graph_catalog",
    "ads_catalog",
    "payments_catalog",
    "growth_catalog",
    "user_state_catalog",
    "governance_catalog",
    "build_catalog_groups",
    "telegram_actions",
    "payments_actions",
    "growth_actions",
    "ads_actions",
    "admin_actions",
    "CANON_ACTION_CATALOG_GROUPS",
]
