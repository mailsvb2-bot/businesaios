from __future__ import annotations

from runtime.messaging.inbound_entrypoint import issue_inbound_message_decision
from runtime.messaging.inbound_strict_owner_guard import assert_inbound_owner


class MessagingInboundDecisionGateway:
    def __init__(self, *, decision_core, caller: str):
        self._decision_core = decision_core
        self._caller = str(caller)

    def process(self, *, message):
        """Canonical inbound-message decision entrypoint.

        Provider/webhook surfaces must call this method rather than reaching into
        DecisionCore directly. ``issue`` remains a compatibility alias below so
        older tests and callers do not create a second decision path.
        """
        assert_inbound_owner(self._caller)
        return issue_inbound_message_decision(
            decision_core=self._decision_core,
            message=message,
        )

    def issue(self, *, message):
        return self.process(message=message)


__all__ = ["MessagingInboundDecisionGateway"]
