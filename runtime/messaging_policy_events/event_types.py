from __future__ import annotations

EVENT_POLICY_PLAN_CREATED = "messaging_policy_plan_created"
EVENT_MESSAGE_ATTEMPTED = "messaging_message_attempted"
EVENT_MESSAGE_DELIVERED = "messaging_message_delivered"
EVENT_MESSAGE_FAILED = "messaging_message_failed"
EVENT_CHANNEL_BLOCKED = "messaging_channel_blocked"
EVENT_POLICY_EXECUTION_FINISHED = "messaging_policy_execution_finished"

MESSAGING_POLICY_EVENT_TYPES = {
    EVENT_POLICY_PLAN_CREATED,
    EVENT_MESSAGE_ATTEMPTED,
    EVENT_MESSAGE_DELIVERED,
    EVENT_MESSAGE_FAILED,
    EVENT_CHANNEL_BLOCKED,
    EVENT_POLICY_EXECUTION_FINISHED,
}
