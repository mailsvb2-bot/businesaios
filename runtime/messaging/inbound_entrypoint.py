from __future__ import annotations

from runtime.decision_path_lock import issue_locked_decision, lock_decision_for_executor
from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state

CANON_MESSAGING_INBOUND_ENTRYPOINT = True


def issue_inbound_message_decision(*, decision_core, message):
    world_input = map_inbound_to_world_state(message)
    envelope = issue_locked_decision(decision_core=decision_core, state=world_input).envelope
    return lock_decision_for_executor(envelope=envelope).envelope


def handle_inbound_message(*, decision_core, message):
    return issue_inbound_message_decision(
        decision_core=decision_core,
        message=message,
    )
