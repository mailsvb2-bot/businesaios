"""Canonical set of operator event-type keys for the Dirac Ring.

Single source of truth: required_operator_keys().
Used by dirac_operators (policy/apply) and tools (audit).
"""

from __future__ import annotations

from typing import Tuple


def required_operator_keys() -> Tuple[str, ...]:
    """Minimal set of event types the OS promises to interpret."""
    return (
        "ui_click",
        "deadline_pressure",
        "price_hard_push",
        "paywall_opened",
        "paywall_closed",
        "offer_shown",
        "offer_clicked",
        "purchase_attempt",
        "purchase_success",
        "purchase_failed",
        "offer_outcome",
        "mood_logged",
        "audio_sent",
        "audio_started",
        "audio_progress",
        "audio_stopped",
        "audio_completed",
        "entitlement_granted",
        "message_sent",
        "message_failed",
        "decision_issued",
        "decision_executed",
        "decision_blocked",
        "ai_decision_trace",
        "data_export",
        "data_delete",
        "rate_limited",
        "pm_artifact_created",
        "pm_feedback_triaged",
        "pm_backlog_prioritized",
        "pm_roadmap_planned",
        "pm_experiment_designed",
        "ads_rl_policy_snapshot@v1",
        "ads_attribution_maturity_snapshot@v1",
        "policy_update_proposed@v1",
        "policy_update_approved@v1",
        "policy_update_applied@v1",
        # Messaging (sync with core.events.event_types.KNOWN_EVENT_TYPES)
        "messaging_policy_plan_created",
        "messaging_message_attempted",
        "messaging_message_delivered",
        "messaging_message_failed",
        "messaging_channel_blocked",
        "messaging_policy_execution_finished",
        # Finance (sync with core.events.event_types.KNOWN_EVENT_TYPES)
        "finance.forecast_revised",
        "finance.scenario_selected",
        "finance.allocation_recommended",
        "finance.job_started",
        "finance.job_completed",
    )


__all__ = ["required_operator_keys"]
