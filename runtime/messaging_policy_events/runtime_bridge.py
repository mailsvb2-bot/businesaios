from __future__ import annotations

from runtime._safe_setattr import safe_setattr
from runtime.messaging_policy_events.event_recorder import MessagingPolicyEventRecorder
from runtime.messaging_policy_events.event_store_adapter import EventLogMessagingPolicyEventStore


def build_policy_event_recorder_from_runtime(runtime_obj):
    store = getattr(runtime_obj, "messaging_policy_event_store", None)
    if store is not None:
        return MessagingPolicyEventRecorder(store=store)

    event_log = getattr(runtime_obj, "event_log", None)
    if event_log is None or not hasattr(event_log, "emit"):
        return None

    store = EventLogMessagingPolicyEventStore(event_log=event_log)
    safe_setattr(runtime_obj, "messaging_policy_event_store", store)
    return MessagingPolicyEventRecorder(store=store)
