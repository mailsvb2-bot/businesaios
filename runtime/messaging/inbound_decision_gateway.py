from __future__ import annotations

from runtime.messaging.inbound_entrypoint import issue_inbound_message_decision
from runtime.messaging.inbound_strict_owner_guard import assert_inbound_owner


class MessagingInboundDecisionGateway:
    def __init__(self, *, decision_core, caller: str):
        self._decision_core = decision_core
        self._caller = str(caller)

    def issue(self, *, message):
        assert_inbound_owner(self._caller)
        return issue_inbound_message_decision(
            decision_core=self._decision_core,
            message=message,
        )
