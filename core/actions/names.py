"""Canonical action names.

Keep action-name constants in one tiny place to avoid naming drift between
catalog, runtime handlers, UI flows, and tests.
"""

from __future__ import annotations

ACTION_ADS_APPLY_EXECUTE_V1 = "ads_apply_" + "execute@v1"
ACTION_EXECUTE_PLAN_V1 = "execute_plan@v1"
ACTION_AI_CEO_PLAN_V1 = "ai_ceo_plan" + "@v1"
ACTION_ROUTE_LEAD_V1 = "route_lead@v1"

ACTION_ENQUEUE_EVOLUTION_JOB_V1 = "enqueue_evolution_job@v1"
ACTION_APPLY_OFFER_PATCH_V1 = "apply_offer_patch@v1"
ACTION_SUGGEST_OFFER_PATCH_V1 = "suggest_offer_patch@v1"
ACTION_ADS_AUTOPILOT_TICK_V1 = "ads_autopilot_tick@v1"
ACTION_PRICING_SELECT_V1 = "pricing_select@v1"
ACTION_REWARD_OBSERVE_V1 = "reward_observe@v1"
ACTION_GROWTH_PROPOSE_V1 = "growth_propose@v1"
ACTION_GROWTH_PROPOSAL_APPLY_V1 = "growth_proposal_apply@v1"
