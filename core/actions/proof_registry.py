"""Action → proof-event registry.

Ring invariant: if an action has irreversible effects, it MUST emit a proof-event.
This registry centralizes the mapping used by:
  - runtime recovery (avoid double side-effects)
  - reward engine (anti-gaming: reward forbidden without proof)

Keep in sync with runtime.boot.handlers_wiring and effects that emit proof events.
Actions not listed here are re-dispatched on recovery (handlers must be idempotent).
"""

from core.actions.names import ACTION_ROUTE_LEAD_V1

ACTION_PROOF_EVENT = {
    "send_message@v1": "message_sent",
    "send_audio@v1": "audio_sent",
    "send_weather@v1": "weather_sent",
    "capture_payment@v1": "payment_captured",
    "create_payment_and_send_link@v1": "payment_captured",
    "deploy_policy@v1": "policy_deployed",
    "rollback_policy@v1": "policy_rolled_back",
    "reconcile_payments@v1": "payments_reconciled",
    "reconcile_payment@v1": "payment_reconciled",
    "grant_access@v1": "access_granted",
    "set_user_setting@v1": "user_setting_set",
    "apply_offer_patch@v1": "offer_patch_applied",
    "suggest_offer_patch@v1": "offer_patch_suggested",
    "log_mood@v1": "mood_logged",
    "select_tariff@v1": "tariff_selected",
    "apply_pricing_change@v1": "pricing_change_applied",
    "request_pricing_change@v1": "pricing_change_requested",
    "reject_pricing_change@v1": "pricing_change_rejected",
    "admin_set_role@v1": "admin_role_set",
    "admin_set_perm@v1": "admin_perm_set",
    # local-only and advisory actions can use the universal execution proof
    "noop@v1": "decision_executed",
    "poll_telegram_updates@v1": "decision_executed",
    ACTION_ROUTE_LEAD_V1: "decision_executed",
}
