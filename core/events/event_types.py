from __future__ import annotations

"""Canonical event type vocabulary (pure).

This is the single source of truth for event type names and normalization.
Storage implementations may import this module, but core code must not depend
on platform_layer paths.
"""

from typing import Dict, Set

UI_CLICK = "ui_click"
PAYWALL_OPENED = "paywall_opened"
PAYWALL_CLOSED = "paywall_closed"
OFFER_SHOWN = "offer_shown"
OFFER_CLICKED = "offer_clicked"
PURCHASE_ATTEMPT = "purchase_attempt"
PURCHASE_SUCCESS = "purchase_success"
PURCHASE_FAILED = "purchase_failed"
OFFER_OUTCOME = "offer_outcome"
MOOD_LOGGED = "mood_logged"
AUDIO_SENT = "audio_sent"
AUDIO_STARTED = "audio_started"
AUDIO_PROGRESS = "audio_progress"
AUDIO_STOPPED = "audio_stopped"
AUDIO_COMPLETED = "audio_completed"
ENTITLEMENT_GRANTED = "entitlement_granted"
MESSAGE_SENT = "message_sent"
MESSAGE_FAILED = "message_failed"

# AI / governance
DECISION_ISSUED = "decision_issued"
DECISION_EXECUTED = "decision_executed"
DECISION_BLOCKED = "decision_blocked"
AI_DECISION_TRACE = "ai_decision_trace"
DATA_EXPORT = "data_export"
DATA_DELETE = "data_delete"
RATE_LIMITED = "rate_limited"

# Product Management
PM_ARTIFACT_CREATED = "pm_artifact_created"
PM_FEEDBACK_TRIAGED = "pm_feedback_triaged"
PM_BACKLOG_PRIORITIZED = "pm_backlog_prioritized"
PM_ROADMAP_PLANNED = "pm_roadmap_planned"
PM_EXPERIMENT_DESIGNED = "pm_experiment_designed"
ADS_RL_POLICY_SNAPSHOT = "ads_rl_policy_snapshot@v1"
ADS_ATTRIBUTION_MATURITY_SNAPSHOT = "ads_attribution_maturity_snapshot@v1"
POLICY_UPDATE_PROPOSED = "policy_update_proposed@v1"
POLICY_UPDATE_APPROVED = "policy_update_approved@v1"
POLICY_UPDATE_APPLIED = "policy_update_applied@v1"
MESSAGING_POLICY_PLAN_CREATED = "messaging_policy_plan_created"
MESSAGING_MESSAGE_ATTEMPTED = "messaging_message_attempted"
MESSAGING_MESSAGE_DELIVERED = "messaging_message_delivered"
MESSAGING_MESSAGE_FAILED = "messaging_message_failed"
MESSAGING_CHANNEL_BLOCKED = "messaging_channel_blocked"
MESSAGING_POLICY_EXECUTION_FINISHED = "messaging_policy_execution_finished"

FINANCE_FORECAST_REVISED = "finance.forecast_revised"
FINANCE_SCENARIO_SELECTED = "finance.scenario_selected"
FINANCE_ALLOCATION_RECOMMENDED = "finance.allocation_recommended"
FINANCE_JOB_STARTED = "finance.job_started"
FINANCE_JOB_COMPLETED = "finance.job_completed"


RETENTION_EVENT_TYPES: Set[str] = {
    PAYWALL_OPENED,
    PAYWALL_CLOSED,
    OFFER_SHOWN,
    OFFER_CLICKED,
    PURCHASE_ATTEMPT,
    PURCHASE_SUCCESS,
    PURCHASE_FAILED,
    OFFER_OUTCOME,
    AUDIO_STARTED,
    AUDIO_PROGRESS,
    AUDIO_STOPPED,
    AUDIO_COMPLETED,
    ENTITLEMENT_GRANTED,
    MESSAGE_SENT,
    MESSAGE_FAILED,
}

KNOWN_EVENT_TYPES: Set[str] = {
    UI_CLICK,
    PAYWALL_OPENED,
    PAYWALL_CLOSED,
    OFFER_SHOWN,
    OFFER_CLICKED,
    PURCHASE_ATTEMPT,
    PURCHASE_SUCCESS,
    PURCHASE_FAILED,
    OFFER_OUTCOME,
    MOOD_LOGGED,
    AUDIO_SENT,
    AUDIO_STARTED,
    AUDIO_PROGRESS,
    AUDIO_STOPPED,
    AUDIO_COMPLETED,
    ENTITLEMENT_GRANTED,
    MESSAGE_SENT,
    MESSAGE_FAILED,
    DECISION_ISSUED,
    DECISION_EXECUTED,
    DECISION_BLOCKED,
    AI_DECISION_TRACE,
    DATA_EXPORT,
    DATA_DELETE,
    RATE_LIMITED,
    PM_ARTIFACT_CREATED,
    PM_FEEDBACK_TRIAGED,
    PM_BACKLOG_PRIORITIZED,
    PM_ROADMAP_PLANNED,
    PM_EXPERIMENT_DESIGNED,
    ADS_RL_POLICY_SNAPSHOT,
    ADS_ATTRIBUTION_MATURITY_SNAPSHOT,
    POLICY_UPDATE_PROPOSED,
    POLICY_UPDATE_APPROVED,
    POLICY_UPDATE_APPLIED,
    MESSAGING_POLICY_PLAN_CREATED,
    MESSAGING_MESSAGE_ATTEMPTED,
    MESSAGING_MESSAGE_DELIVERED,
    MESSAGING_MESSAGE_FAILED,
    MESSAGING_CHANNEL_BLOCKED,
    MESSAGING_POLICY_EXECUTION_FINISHED,
    FINANCE_FORECAST_REVISED,
    FINANCE_SCENARIO_SELECTED,
    FINANCE_ALLOCATION_RECOMMENDED,
    FINANCE_JOB_STARTED,
    FINANCE_JOB_COMPLETED,

}


ALIASES: Dict[str, str] = {
    "paywall_open": PAYWALL_OPENED,
    "paywall_close": PAYWALL_CLOSED,
    "offer_click_primary": OFFER_CLICKED,
    "offer_click_secondary": OFFER_CLICKED,
}


def normalize_event_type(event_type: str) -> str:
    et = (event_type or "").strip()
    if not et:
        return ""
    return ALIASES.get(et, et)


def is_known(event_type: str) -> bool:
    return normalize_event_type(event_type) in KNOWN_EVENT_TYPES


__all__ = [name for name in globals() if name.isupper()] + ["normalize_event_type", "is_known"]
