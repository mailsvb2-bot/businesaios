from __future__ import annotations

from application.headless.models import CEOParticipation, GoalExecutionRequest

CANON_REAL_HEADLESS_SCENARIOS = True


def scenario_names() -> tuple[str, ...]:
    return (
        "acquire_client",
        "pricing_adjustment",
        "lead_processing",
        "mini_funnel_launch",
        "retention_recovery",
    )


def build_named_scenario(
    *,
    name: str,
    business_id: str,
    tenant_id: str,
    user_id: str | None,
) -> GoalExecutionRequest:
    builders = {
        "acquire_client": build_acquire_client_scenario,
        "pricing_adjustment": build_pricing_adjustment_scenario,
        "lead_processing": build_lead_processing_scenario,
        "mini_funnel_launch": build_mini_funnel_launch_scenario,
        "retention_recovery": build_retention_recovery_scenario,
    }
    try:
        builder = builders[name]
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {name}") from exc
    return builder(
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )


def build_acquire_client_scenario(*, business_id: str, tenant_id: str, user_id: str | None) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="get 10 clients",
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
        region="EU",
        profile={
            "goal": "client_acquisition",
            "region": "EU",
            "channel_preference": "multichannel",
        },
        signals=[
            {"kind": "demand_drop", "value": 0.18},
            {"kind": "lead_velocity", "value": 3},
        ],
        constraints={
            "budget_cap_daily": 120,
            "risk_mode": "conservative",
        },
        economy={
            "cash_on_hand": 2500,
            "target_cac": 35,
        },
        meta={"scenario": "acquire_client"},
        max_steps=3,
    )


def build_pricing_adjustment_scenario(*, business_id: str, tenant_id: str, user_id: str | None) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="stabilize margin without killing conversion",
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
        region="EU",
        profile={
            "goal": "pricing_adjustment",
            "region": "EU",
            "segment": "local_services",
        },
        signals=[
            {"kind": "margin_pressure", "value": 0.22},
            {"kind": "conversion_rate", "value": 0.06},
        ],
        constraints={
            "max_price_delta_pct": 8,
            "price_band": "standard",
        },
        economy={
            "gross_margin": 0.19,
            "target_margin": 0.27,
        },
        meta={"scenario": "pricing_adjustment"},
        ceo=CEOParticipation(enabled=True, objective="restore margin", horizon="14d"),
        max_steps=2,
    )


def build_lead_processing_scenario(*, business_id: str, tenant_id: str, user_id: str | None) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="process inbound leads and prioritize hot ones",
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
        region="EU",
        profile={
            "goal": "lead_processing",
            "region": "EU",
            "sla_minutes": 10,
        },
        signals=[
            {"kind": "new_leads", "value": 17},
            {"kind": "hot_leads", "value": 5},
        ],
        constraints={
            "max_unanswered_minutes": 15,
            "risk_mode": "safe",
        },
        economy={"pipeline_value": 1800},
        meta={"scenario": "lead_processing"},
        max_steps=2,
    )


def build_mini_funnel_launch_scenario(*, business_id: str, tenant_id: str, user_id: str | None) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="launch mini funnel for dormant demand",
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
        region="EU",
        profile={
            "goal": "mini_funnel_launch",
            "region": "EU",
            "offer_type": "reactivation_offer",
        },
        signals=[
            {"kind": "inactive_users", "value": 240},
            {"kind": "recent_orders", "value": 8},
        ],
        constraints={
            "discount_cap_pct": 12,
            "message_frequency_cap": 2,
        },
        economy={"expected_revenue_uplift": 500},
        meta={"scenario": "mini_funnel_launch"},
        ceo=CEOParticipation(enabled=True, objective="reactivate dormant demand", horizon="21d"),
        max_steps=3,
    )


def build_retention_recovery_scenario(*, business_id: str, tenant_id: str, user_id: str | None) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="reduce churn risk in high-value cohort",
        business_id=business_id,
        tenant_id=tenant_id,
        user_id=user_id,
        region="EU",
        profile={
            "goal": "retention_recovery",
            "region": "EU",
            "cohort": "high_value",
        },
        signals=[
            {"kind": "churn_risk_users", "value": 21},
            {"kind": "ltv_median", "value": 430},
        ],
        constraints={
            "retention_budget_cap": 300,
            "channel_whitelist": ["email", "telegram", "ads"],
        },
        economy={"expected_saved_revenue": 1700},
        meta={"scenario": "retention_recovery"},
        ceo=CEOParticipation(enabled=True, objective="save high value cohort", horizon="30d"),
        max_steps=3,
    )


__all__ = [
    "CANON_REAL_HEADLESS_SCENARIOS",
    "build_acquire_client_scenario",
    "build_lead_processing_scenario",
    "build_mini_funnel_launch_scenario",
    "build_named_scenario",
    "build_pricing_adjustment_scenario",
    "build_retention_recovery_scenario",
    "scenario_names",
]
